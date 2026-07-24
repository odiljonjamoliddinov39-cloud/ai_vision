"""Export YOLO training data from saved Result Analytics visual evidence.

The exporter reads catalog recognition history, finds camera frame URLs and
bounding boxes saved in `camera_counts`, then writes full-frame images plus
YOLO-format labels into a dataset folder.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
import sys
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database.catalog_db import CatalogDB  # noqa: E402


@dataclass(frozen=True)
class ExportReport:
    image_count: int
    label_count: int
    skipped_count: int
    dataset_root: Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def safe_slug(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._-") or "sample"


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)


def resolve_dataset_root(data_yaml: Path, data: dict[str, Any]) -> Path:
    configured = Path(str(data.get("path") or data_yaml.parent))
    if configured.is_absolute():
        return configured.resolve()
    root_candidate = (repo_root() / configured).resolve()
    if root_candidate.exists():
        return root_candidate
    return (data_yaml.parent / configured).resolve()


def class_names(data: dict[str, Any]) -> dict[int, str]:
    raw_names = data.get("names") or {}
    if isinstance(raw_names, list):
        return {index: str(name) for index, name in enumerate(raw_names)}
    if isinstance(raw_names, dict):
        return {int(index): str(name) for index, name in raw_names.items()}
    raise ValueError("Dataset YAML must define names as a list or mapping.")


def class_id_for_item(item_name: str, names: dict[int, str], include_new_classes: bool) -> int | None:
    target = normalize(item_name)
    for class_id, class_name in names.items():
        if normalize(class_name) == target:
            return class_id
    if not include_new_classes:
        return None
    next_id = (max(names) + 1) if names else 0
    names[next_id] = item_name
    return next_id


def snapshot_path_from_url(snapshot_dir: Path, url: str) -> Path | None:
    path = unquote(urlsplit(str(url or "")).path)
    if not path.startswith("/snapshots/"):
        return None
    relative = Path(path.removeprefix("/snapshots/"))
    candidate = (snapshot_dir / relative).resolve()
    try:
        candidate.relative_to(snapshot_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def image_size(path: Path) -> tuple[int, int]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python-headless is required to export YOLO samples.") from exc

    frame = cv2.imread(str(path))
    if frame is None:
        raise ValueError(f"Could not read image: {path}")
    height, width = frame.shape[:2]
    return int(width), int(height)


def yolo_box(class_id: int, bbox: dict[str, Any], width: int, height: int) -> str | None:
    try:
        x1 = float(bbox["x1"])
        y1 = float(bbox["y1"])
        x2 = float(bbox["x2"])
        y2 = float(bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return None

    x1 = max(0.0, min(float(width), x1))
    y1 = max(0.0, min(float(height), y1))
    x2 = max(0.0, min(float(width), x2))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None

    x_center = ((x1 + x2) / 2.0) / width
    y_center = ((y1 + y2) / 2.0) / height
    box_width = (x2 - x1) / width
    box_height = (y2 - y1) / height
    return f"{class_id} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"


def split_for_key(key: str, split: str, val_ratio: float) -> str:
    if split in {"train", "val"}:
        return split
    digest = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16)
    ratio = digest / 0xFFFFFFFF
    return "val" if ratio < max(0.0, min(0.9, val_ratio)) else "train"


def export_groups(
    results: list[dict[str, Any]],
    names: dict[int, str],
    args: argparse.Namespace,
) -> tuple[dict[tuple[str, Path], set[str]], int]:
    snapshot_dir = Path(args.snapshot_dir)
    groups: dict[tuple[str, Path], set[str]] = {}
    skipped = 0
    item_filter = normalize(args.item)
    for result in results:
        item_name = str(result.get("item_name") or "")
        if item_filter and item_filter not in normalize(item_name):
            continue
        if float(result.get("confidence") or 0.0) < args.min_confidence:
            skipped += 1
            continue
        class_id = class_id_for_item(item_name, names, args.include_new_classes)
        if class_id is None:
            skipped += 1
            continue
        for entry in result.get("camera_counts") or []:
            frame_path = snapshot_path_from_url(snapshot_dir, str(entry.get("frame_url") or ""))
            if frame_path is None:
                skipped += 1
                continue
            width, height = image_size(frame_path)
            label = yolo_box(class_id, entry.get("bbox") or {}, width, height)
            if label is None:
                skipped += 1
                continue
            split = split_for_key(f"{result.get('run_id')}:{frame_path}:{label}", args.split, args.val_ratio)
            groups.setdefault((split, frame_path), set()).add(label)
    return groups, skipped


def build_dataset(args: argparse.Namespace) -> ExportReport:
    data_yaml = Path(args.data_yaml)
    data = read_yaml(data_yaml)
    dataset_root = Path(args.dataset).resolve() if args.dataset else resolve_dataset_root(data_yaml, data)
    names = class_names(data)

    db = CatalogDB(str(args.catalog_db))
    results = db.result_history(args.scope_id, limit=args.limit)
    groups, skipped = export_groups(results, names, args)

    if args.include_new_classes:
        data["names"] = {index: names[index] for index in sorted(names)}
        write_yaml(data_yaml, data)

    image_count = 0
    label_count = 0
    for (split, source), labels in sorted(groups.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        digest = hashlib.sha1(f"{source.resolve()}:{','.join(sorted(labels))}".encode("utf-8")).hexdigest()[:10]
        stem = f"result_{digest}_{safe_slug(source.stem)}"
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        target_image = image_dir / f"{stem}{source.suffix.lower()}"
        target_label = label_dir / f"{stem}.txt"
        if not args.dry_run:
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target_image)
            target_label.write_text("\n".join(sorted(labels)) + "\n", encoding="utf-8")
        image_count += 1
        label_count += len(labels)

    return ExportReport(image_count, label_count, skipped, dataset_root)


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Export YOLO dataset from saved Result Analytics evidence.")
    parser.add_argument("--catalog-db", default=str(root / "database" / "catalog.db"))
    parser.add_argument("--scope-id", default="warehouse-a")
    parser.add_argument("--snapshot-dir", default=str(root / "snapshots"))
    parser.add_argument("--data-yaml", default=str(root / "datasets" / "baget_box" / "data.yaml"))
    parser.add_argument("--dataset", default=None, help="Override dataset root. Defaults to data.yaml path.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--split", choices=["auto", "train", "val"], default="auto")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--min-confidence", type=float, default=0.2)
    parser.add_argument("--item", default=None, help="Optional item-name filter, for example 'Baget Box'.")
    parser.add_argument("--include-new-classes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    report = build_dataset(parse_args())
    print(
        f"Exported {report.image_count} image(s), {report.label_count} label row(s), "
        f"skipped {report.skipped_count}; dataset: {report.dataset_root}"
    )
