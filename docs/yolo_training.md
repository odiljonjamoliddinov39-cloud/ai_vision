# YOLO Training for Baget Box

This project can use two detection modes:

1. `yolov8s-world.pt` with text prompts. Fast to tune, no training required.
2. A custom YOLO detector trained on the real `baget box` camera images.

Use this guide for the custom detector path.

## 1. Collect Images

Put real camera images here:

```text
datasets/baget_box/images/train/
datasets/baget_box/images/val/
```

Recommended first dataset:

- 200-500 labeled images minimum
- 80% train, 20% val
- images from the same NVR/camera angles used in production
- single boxes, stacks, far views, close views
- different lighting and occlusion

You can bootstrap images and draft YOLO labels from the running detector:

```bash
python scripts/collect_yolo_samples.py --split train
python scripts/collect_yolo_samples.py --split val
```

The collector reads `logs/detection_health.json`, copies the latest camera
frames from `snapshots/`, and writes labels for detections that look like boxes.
Review these labels before final training; they are useful drafts, not a
replacement for human annotation.

You can also export samples from the saved **Result Analytics** evidence. This
uses the camera frame and bbox saved during new recognition runs:

```bash
python scripts/export_yolo_dataset_from_results.py --item "Baget Box"
```

Use `--split train` or `--split val` when you want to force where the exported
frames go. Without it, the exporter keeps an automatic 80/20 train/val split.
Run **Run recognition now** in Result Analytics several times before exporting
so the database contains enough camera angles and object examples.

## 2. Label Boxes

Create matching label files:

```text
datasets/baget_box/images/train/frame_001.jpg
datasets/baget_box/labels/train/frame_001.txt
```

Each row is:

```text
0 x_center y_center width height
```

Values are normalized from 0 to 1. Class `0` means `baget box`.

Good tools for labeling:

- CVAT
- Label Studio
- Roboflow
- Ultralytics Platform

Export labels in YOLO detection format.

## 3. Validate Dataset

```bash
python scripts/train_yolo.py --validate-only
```

If this reports missing images or labels, fix the dataset before training.

## 4. Train

GPU:

```bash
python scripts/train_yolo.py --device 0 --epochs 100 --imgsz 960 --batch 8
```

CPU fallback:

```bash
python scripts/train_yolo.py --device cpu --epochs 50 --imgsz 640 --batch 2
```

The script copies the trained model to:

```text
models/baget_box_best.pt
```

## 5. Apply to AI Vision

After training, update runtime config automatically:

```bash
python scripts/train_yolo.py --device 0 --epochs 100 --imgsz 960 --batch 8 --apply-config config/config.yaml
```

This sets:

```yaml
detection:
  model_path: models/baget_box_best.pt
  confidence_threshold: 0.25
  image_size: 960
  classes: null
  class_prompts: null
```

Restart backend/detector, then click **Run recognition now** in Result Analytics.

## 6. Improve Result Accuracy

`Run recognition now` samples several fresh frames and keeps the best object
count per camera. Tune these environment variables when cameras are slow or
boxes are missed:

```bash
CATALOG_RECOGNITION_SAMPLES=3
CATALOG_RECOGNITION_SAMPLE_INTERVAL_SECONDS=0.2
CATALOG_YOLO_IMAGE_SIZE=1280
CATALOG_YOLO_CONFIDENCE_THRESHOLD=0.01
```

Increase `CATALOG_RECOGNITION_SAMPLES` to 5-8 for more stable counts. Increase
`CATALOG_YOLO_IMAGE_SIZE` when boxes are small or far away. Lower
`CATALOG_YOLO_CONFIDENCE_THRESHOLD` only when the model misses real boxes.

## Notes

Do not commit dataset images, labels, training runs, or `.pt` files to git.
They are intentionally ignored by `.gitignore`.
