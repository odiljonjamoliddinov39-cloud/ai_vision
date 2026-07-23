# Baget Box YOLO Dataset

Use this folder for custom YOLO training of the `baget box` class.

Expected structure:

```text
datasets/baget_box/
  data.yaml
  images/train/
  images/val/
  labels/train/
  labels/val/
```

Each image needs a matching YOLO label file with the same basename:

```text
images/train/camera_001.jpg
labels/train/camera_001.txt
```

Label rows use normalized YOLO detection format:

```text
0 x_center y_center width height
```

Example, one centered box occupying half the frame:

```text
0 0.5 0.5 0.5 0.5
```

Recommended minimum for the first useful model:

- 200-500 labeled images
- images from the real NVR cameras
- close and far views
- single boxes and stacks
- different lighting and angles
- boxes partially hidden by other boxes

Dataset images and label files are ignored by git on purpose. Keep them in
Codespace, external storage, or a dataset tool; commit only this template.

To collect draft samples from the running detector:

```bash
python scripts/collect_yolo_samples.py --split train
python scripts/collect_yolo_samples.py --split val
```

Always review generated labels before training.
