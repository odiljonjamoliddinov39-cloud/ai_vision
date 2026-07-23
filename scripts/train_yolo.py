"""Train a custom YOLO detector for AI Vision catalog items.

The script intentionally imports Ultralytics only after validating the dataset
so basic checks can run in lightweight environments.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any

import yaml


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class SplitReport:
    name: str
    image_dir: Path
    label_dir: Path
    image_count: int
    label_count: int
    missing_label_count: int


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)


def resolve_dataset_root(dataset_yaml: Path, data: dict[str, Any]) -> Path:
    configured = Path(str(data.get("path") or dataset_yaml.parent))
    if configured.is_absolute():
        return configured

    root_candidate = (repo_root() / configured).resolve()
    if root_candidate.exists():
        return root_candidate

    return (dataset_yaml.parent / configured).resolve()


def resolve_split_dir(dataset_root: Path, split_value: Any) -> Path:
    if isinstance(split_value, list):
        if len(split_value) != 1:
            raise ValueError("This training helper expects one directory per split.")
        split_value = split_value[0]
    split_path = Path(str(split_value))
    return split_path if split_path.is_absolute() else (dataset_root / split_path).resolve()


def label_dir_for_images(dataset_root: Path, image_dir: Path) -> Path:
    try:
        relative = image_dir.relative_to(dataset_root)
    except ValueError:
        return image_dir.parent.parent / "labels" / image_dir.name

    parts = list(relative.parts)
    if parts and parts[0] == "images":
        parts[0] = "labels"
        return (dataset_root / Path(*parts)).resolve()
    return (dataset_root / "labels" / image_dir.name).resolve()


def image_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(file for file in path.iterdir() if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS)


def validate_label_file(path: Path) -> None:
    if not path.exists():
        return
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_number} must have 5 fields: class cx cy w h")
        class_id = int(parts[0])
        if class_id < 0:
            raise ValueError(f"{path}:{line_number} class id must be zero or greater")
        values = [float(value) for value in parts[1:]]
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError(f"{path}:{line_number} box values must be normalized from 0 to 1")


def validate_dataset(dataset_yaml: Path) -> list[SplitReport]:
    data = read_yaml(dataset_yaml)
    if "names" not in data or not data["names"]:
        raise ValueError(f"{dataset_yaml} must define class names under 'names'.")

    dataset_root = resolve_dataset_root(dataset_yaml, data)
    reports: list[SplitReport] = []
    for split_name in ("train", "val"):
        if split_name not in data:
            raise ValueError(f"{dataset_yaml} must define '{split_name}'.")
        image_dir = resolve_split_dir(dataset_root, data[split_name])
        label_dir = label_dir_for_images(dataset_root, image_dir)
        images = image_files(image_dir)
        labels = sorted(label_dir.glob("*.txt")) if label_dir.exists() else []
        missing = 0
        for image in images:
            label_path = label_dir / f"{image.stem}.txt"
            if not label_path.exists():
                missing += 1
                continue
            validate_label_file(label_path)
        reports.append(
            SplitReport(
                name=split_name,
                image_dir=image_dir,
                label_dir=label_dir,
                image_count=len(images),
                label_count=len(labels),
                missing_label_count=missing,
            )
        )

    for report in reports:
        if report.image_count == 0:
            raise ValueError(f"No {report.name} images found in {report.image_dir}")
        if report.label_count == 0:
            raise ValueError(f"No {report.name} labels found in {report.label_dir}")
    return reports


def update_runtime_config(config_path: Path, model_path: Path, image_size: int, confidence: float) -> None:
    config = read_yaml(config_path)
    detection = config.setdefault("detection", {})
    try:
        model_value = model_path.resolve().relative_to(repo_root()).as_posix()
    except ValueError:
        model_value = model_path.as_posix()

    detection["model_path"] = model_value
    detection["confidence_threshold"] = confidence
    detection["image_size"] = image_size
    detection["classes"] = None
    detection["class_prompts"] = None
    write_yaml(config_path, config)


def train(args: argparse.Namespace) -> Path:
    dataset_yaml = Path(args.dataset).resolve()
    reports = validate_dataset(dataset_yaml)
    for report in reports:
        print(
            f"{report.name}: {report.image_count} images, {report.label_count} labels, "
            f"{report.missing_label_count} missing labels"
        )
    if args.validate_only:
        return Path()

    from ultralytics import YOLO

    model = YOLO(args.base_model)
    results = model.train(
        data=str(dataset_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=args.patience,
        exist_ok=True,
    )
    save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.name))
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(f"Training finished, but best weights were not found at {best}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, output)
    print(f"Copied trained weights to {output}")

    if args.apply_config:
        update_runtime_config(Path(args.apply_config), output, args.imgsz, args.runtime_confidence)
        print(f"Updated runtime detection config: {args.apply_config}")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLO for the AI Vision Baget Box detector.")
    parser.add_argument("--dataset", default="datasets/baget_box/data.yaml", help="YOLO dataset YAML path.")
    parser.add_argument("--base-model", default="yolov8s.pt", help="Pretrained model to fine-tune.")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0", help="'0' for first GPU, 'cpu' for CPU.")
    parser.add_argument("--project", default="runs/detect")
    parser.add_argument("--name", default="baget_box")
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--output", default="models/baget_box_best.pt")
    parser.add_argument("--apply-config", default=None, help="Optional runtime config path to update after training.")
    parser.add_argument("--runtime-confidence", type=float, default=0.25)
    parser.add_argument("--validate-only", action="store_true", help="Validate dataset without training.")
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
