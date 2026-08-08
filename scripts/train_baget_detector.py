"""Train an authoritative one-class product detector from verified labels."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def paired_count(root: Path, split: str) -> int:
    images = root / "images" / split
    labels = root / "labels" / split
    image_stems = {path.stem for path in images.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}
    label_stems = {path.stem for path in labels.glob("*.txt")}
    missing = sorted(image_stems - label_stems)
    if missing:
        raise SystemExit(f"Missing YOLO labels for {split}: {', '.join(missing[:10])}")
    return len(image_stems)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="datasets/baget_box/data.yaml")
    parser.add_argument("--base-model", default="yolov8s.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--output", default="models/baget_box_best.pt")
    args = parser.parse_args()
    data = Path(args.data).resolve()
    root = data.parent
    train_count, val_count = paired_count(root, "train"), paired_count(root, "val")
    if train_count < 20 or val_count < 5:
        raise SystemExit("Product training requires at least 20 labeled train and 5 labeled validation images.")
    from ultralytics import YOLO

    run = YOLO(args.base_model).train(
        data=str(data), epochs=args.epochs, imgsz=args.image_size,
        project="runs/product_models", name=Path(args.output).parent.name, exist_ok=False,
    )
    best = Path(run.save_dir) / "weights" / "best.pt"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, output)
    print(f"Authoritative product detector written to {output}")


if __name__ == "__main__":
    main()
