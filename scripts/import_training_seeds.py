"""Import reviewed, versioned samples into the persistent YOLO dataset once."""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests


SEED_ROOT = Path("/app/training_seeds/baget_box_stack_individual")
MARKER_ROOT = Path("/app/datasets/.seeded")
ANNOTATE_URL = "http://127.0.0.1:8080/api/training/annotate"


def _post_seed(image: Path, metadata: Path) -> int:
    boxes = json.loads(metadata.read_text(encoding="utf-8"))
    if not boxes:
        raise RuntimeError(f"Seed has no annotations: {metadata}")
    last_error: Exception | None = None
    for _ in range(30):
        try:
            with image.open("rb") as image_file:
                response = requests.post(
                    ANNOTATE_URL,
                    data={"split": "train", "boxes": json.dumps(boxes)},
                    files={"file": (image.name, image_file, "image/jpeg")},
                    timeout=30,
                )
            response.raise_for_status()
            return int(response.json().get("labeled", 0))
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Backend never accepted {image.name}: {last_error}")


def main() -> None:
    if not SEED_ROOT.is_dir():
        raise RuntimeError(f"Training seed directory is missing: {SEED_ROOT}")
    MARKER_ROOT.mkdir(parents=True, exist_ok=True)
    metadata_files = sorted(SEED_ROOT.glob("*.boxes.json"))
    if not metadata_files:
        raise RuntimeError(f"No training seed metadata found under {SEED_ROOT}")

    for metadata in metadata_files:
        stem = metadata.name.removesuffix(".boxes.json")
        image = SEED_ROOT / f"{stem}.jpg"
        marker = MARKER_ROOT / f"{stem}.v1"
        if marker.exists():
            print(f"Training seed already imported: {stem}", flush=True)
            continue
        if not image.is_file():
            raise RuntimeError(f"Training seed image is missing: {image}")
        labeled = _post_seed(image, metadata)
        marker.write_text(f"labels={labeled}\n", encoding="utf-8")
        print(f"Imported training seed: {stem} ({labeled} boxes)", flush=True)


if __name__ == "__main__":
    main()
