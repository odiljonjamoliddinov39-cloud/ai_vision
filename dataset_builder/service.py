"""Product-oriented dataset lifecycle backed by the shared VisionDB."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from database.vision_db import VisionDB


class DatasetError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not result:
        raise DatasetError("Product name cannot produce an empty detector class.")
    return result


def _dhash(image: np.ndarray) -> str:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    return f"{sum(int(bit) << index for index, bit in enumerate(bits.flatten())):016x}"


def _distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


class DatasetBuilder:
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, root: Path, database: VisionDB):
        self.root = Path(root)
        self.database = database
        self.source_root = self.root / "dataset_sources"
        self.dataset_root = self.root / "datasets"
        self.model_root = self.root / "models" / "dataset_builder"
        self.source_root.mkdir(parents=True, exist_ok=True)

    def create_dataset(self, product_id: str, product_name: str) -> dict:
        class_name = _slug(product_name)
        prior = self.database.dataset_fetchone(
            "SELECT MAX(version) AS version FROM vision_datasets WHERE product_id=?",
            (str(product_id),),
        )
        version = int((prior or {}).get("version") or 0) + 1
        dataset_id = f"{class_name}_v{version}_{uuid.uuid4().hex[:8]}"
        now = _now()
        self.database.dataset_execute(
            "INSERT INTO vision_datasets(id,product_id,product_name,class_name,version,status,archived,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (dataset_id, str(product_id), product_name.strip(), class_name, version, "LABELING", 0, now, now),
        )
        (self.source_root / dataset_id).mkdir(parents=True, exist_ok=True)
        return self.get_dataset(dataset_id)

    def list_datasets(self, include_archived: bool = False) -> list[dict]:
        where = "" if include_archived else " WHERE d.archived=0"
        rows = self.database.dataset_fetchall(
            "SELECT d.*, COUNT(i.id) AS images, COALESCE(SUM(i.instance_count),0) AS instances "
            "FROM vision_datasets d LEFT JOIN vision_dataset_images i ON i.dataset_id=d.id" +
            where + " GROUP BY d.id ORDER BY d.updated_at DESC"
        )
        return rows

    def get_dataset(self, dataset_id: str) -> dict:
        row = self.database.dataset_fetchone(
            "SELECT d.*, COUNT(i.id) AS images, COALESCE(SUM(i.instance_count),0) AS instances "
            "FROM vision_datasets d LEFT JOIN vision_dataset_images i ON i.dataset_id=d.id "
            "WHERE d.id=? GROUP BY d.id", (dataset_id,),
        )
        if row is None:
            raise DatasetError("Dataset not found.")
        return row

    def images(self, dataset_id: str) -> list[dict]:
        self.get_dataset(dataset_id)
        return self.database.dataset_fetchall(
            "SELECT * FROM vision_dataset_images WHERE dataset_id=? ORDER BY created_at", (dataset_id,)
        )

    def get_image(self, dataset_id: str, image_id: str) -> dict:
        row = self.database.dataset_fetchone(
            "SELECT * FROM vision_dataset_images WHERE id=? AND dataset_id=?", (image_id, dataset_id)
        )
        if row is None:
            raise DatasetError("Dataset image not found.")
        row["annotations"] = self.database.dataset_fetchall(
            "SELECT * FROM vision_dataset_annotations WHERE image_id=? ORDER BY created_at", (image_id,)
        )
        return row

    def ingest(self, dataset_id: str, content: bytes, *, suffix: str, source: str,
               camera_id: str | None = None, block_id: str | None = None) -> dict:
        dataset = self.get_dataset(dataset_id)
        suffix = suffix.lower()
        if suffix not in self.allowed_extensions:
            raise DatasetError("Only JPG, JPEG, PNG, and WEBP images are supported.")
        array = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise DatasetError("The supplied file is not a readable image.")
        content_hash, perceptual_hash = hashlib.sha256(content).hexdigest(), _dhash(image)
        existing = self.database.dataset_fetchall(
            "SELECT id,perceptual_hash FROM vision_dataset_images WHERE dataset_id=?", (dataset_id,)
        )
        duplicate = next((row for row in existing if _distance(perceptual_hash, row["perceptual_hash"]) <= 4), None)
        if duplicate:
            return {"skipped": True, "reason": "near_duplicate", "duplicate_of": duplicate["id"]}
        image_id = uuid.uuid4().hex
        target = self.source_root / dataset_id / f"{image_id}{suffix}"
        target.write_bytes(content)
        now = _now()
        self.database.dataset_execute(
            "INSERT INTO vision_dataset_images(id,dataset_id,camera_id,block_id,source,original_path,content_hash,perceptual_hash,capture_timestamp,annotation_status,instance_count,split,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (image_id, dataset_id, camera_id, block_id, source, str(target), content_hash,
             perceptual_hash, now, "UNVERIFIED", 0, None, now, now),
        )
        self.database.dataset_execute("UPDATE vision_datasets SET updated_at=? WHERE id=?", (now, dataset_id))
        return {"skipped": False, **self.get_image(dataset_id, image_id), "class_name": dataset["class_name"]}

    def save_annotations(self, dataset_id: str, image_id: str, annotations: list[dict]) -> dict:
        dataset, image = self.get_dataset(dataset_id), self.get_image(dataset_id, image_id)
        self.database.dataset_execute("DELETE FROM vision_dataset_annotations WHERE image_id=?", (image_id,))
        now = _now()
        for annotation in annotations:
            coords = [float(annotation[key]) for key in ("x1", "y1", "x2", "y2")]
            if not all(0.0 <= value <= 1.0 for value in coords) or coords[2] <= coords[0] or coords[3] <= coords[1]:
                raise DatasetError("Bounding boxes must be normalized valid rectangles.")
            provenance = str(annotation.get("provenance") or "manual")
            if provenance not in {"manual", "ai_suggested_approved", "ai_suggested_modified", "ai_suggested"}:
                raise DatasetError("Unsupported annotation provenance.")
            status = "UNVERIFIED" if provenance == "ai_suggested" else "VERIFIED_PENDING_FRAME"
            self.database.dataset_execute(
                "INSERT INTO vision_dataset_annotations(id,image_id,class_name,x1,y1,x2,y2,provenance,status,confidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, image_id, dataset["class_name"], *coords, provenance, status,
                 annotation.get("confidence"), now, now),
            )
        self.database.dataset_execute(
            "UPDATE vision_dataset_images SET annotation_status='UNVERIFIED',instance_count=?,updated_at=? WHERE id=?",
            (len(annotations), now, image["id"]),
        )
        return self.get_image(dataset_id, image_id)

    def approve(self, dataset_id: str, image_id: str) -> dict:
        image = self.get_image(dataset_id, image_id)
        annotations = image["annotations"]
        if any(row["status"] == "UNVERIFIED" for row in annotations):
            raise DatasetError("AI suggestions must be accepted, corrected, or deleted before approval.")
        now = _now()
        self.database.dataset_execute(
            "UPDATE vision_dataset_annotations SET status='VERIFIED',updated_at=? WHERE image_id=?", (now, image_id)
        )
        self.database.dataset_execute(
            "UPDATE vision_dataset_images SET annotation_status='VERIFIED',instance_count=?,updated_at=? WHERE id=?",
            (len(annotations), now, image_id),
        )
        self.materialize(dataset_id)
        return self.get_image(dataset_id, image_id)

    def reject(self, dataset_id: str, image_id: str) -> None:
        image = self.get_image(dataset_id, image_id)
        self.database.dataset_execute("DELETE FROM vision_dataset_annotations WHERE image_id=?", (image_id,))
        self.database.dataset_execute("DELETE FROM vision_dataset_images WHERE id=?", (image_id,))
        Path(image["original_path"]).unlink(missing_ok=True)

    def materialize(self, dataset_id: str) -> Path:
        dataset = self.get_dataset(dataset_id)
        root = self.dataset_root / dataset["class_name"] / f"v{dataset['version']}"
        for split in ("train", "val"):
            (root / "images" / split).mkdir(parents=True, exist_ok=True)
            (root / "labels" / split).mkdir(parents=True, exist_ok=True)
        verified = self.database.dataset_fetchall(
            "SELECT * FROM vision_dataset_images WHERE dataset_id=? AND annotation_status='VERIFIED' ORDER BY perceptual_hash,id",
            (dataset_id,),
        )
        # Build explicit similarity clusters so a near-duplicate pair can never
        # leak across train and validation. Whole clusters are assigned in an
        # approximately 80/20, deterministic split.
        clusters: list[list[dict]] = []
        for image in verified:
            cluster = next(
                (group for group in clusters if any(_distance(image["perceptual_hash"], member["perceptual_hash"]) <= 6 for member in group)),
                None,
            )
            (cluster if cluster is not None else clusters.append([image]))
            if cluster is not None:
                cluster.append(image)
        split_by_id: dict[str, str] = {}
        val_target = round(len(verified) * 0.2)
        val_count = 0
        for index, cluster in enumerate(sorted(clusters, key=lambda group: group[0]["perceptual_hash"])):
            use_val = val_count < val_target and (index % 5 == 0 or len(clusters) - index <= val_target - val_count)
            split = "val" if use_val else "train"
            if use_val:
                val_count += len(cluster)
            split_by_id.update({member["id"]: split for member in cluster})
        for image in verified:
            split = split_by_id[image["id"]]
            source = Path(image["original_path"])
            target = root / "images" / split / source.name
            shutil.copy2(source, target)
            boxes = self.database.dataset_fetchall(
                "SELECT * FROM vision_dataset_annotations WHERE image_id=? AND status='VERIFIED'", (image["id"],)
            )
            lines = []
            for box in boxes:
                width, height = box["x2"] - box["x1"], box["y2"] - box["y1"]
                lines.append(f"0 {(box['x1'] + box['x2']) / 2:.8f} {(box['y1'] + box['y2']) / 2:.8f} {width:.8f} {height:.8f}")
            (root / "labels" / split / f"{source.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            self.database.dataset_execute("UPDATE vision_dataset_images SET split=? WHERE id=?", (split, image["id"]))
        data = {"path": str(root.resolve()), "train": "images/train", "val": "images/val", "names": {0: dataset["class_name"]}}
        (root / "dataset.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return root

    def health(self, dataset_id: str) -> dict:
        dataset = self.get_dataset(dataset_id)
        rows = self.images(dataset_id)
        verified = [row for row in rows if row["annotation_status"] == "VERIFIED"]
        cameras = {row["camera_id"] for row in verified if row["camera_id"]}
        blocks = {row["block_id"] for row in verified if row["block_id"]}
        return {
            "dataset": dataset, "images": len(rows), "verified_images": len(verified),
            "instances": sum(int(row["instance_count"]) for row in verified),
            "labeled_percent": round(100 * len(verified) / len(rows), 1) if rows else 0.0,
            "classes": 1, "train": sum(row["split"] == "train" for row in verified),
            "validation": sum(row["split"] == "val" for row in verified),
            "coverage": {
                "camera_diversity": "GOOD" if len(cameras) >= 3 else "NEEDS MORE",
                "block_diversity": "GOOD" if len(blocks) >= 2 else "NEEDS MORE",
                "lighting_variety": "REVIEW REQUIRED", "angle_diversity": "REVIEW REQUIRED",
                "stacked_objects": "REVIEW REQUIRED", "partial_occlusion": "REVIEW REQUIRED",
                "low_light": "REVIEW REQUIRED",
            },
        }


class DatasetTrainingManager:
    """Runs real Ultralytics training jobs; status comes from the process, not estimates."""

    def __init__(self, builder: DatasetBuilder):
        self.builder = builder
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen] = {}

    def start(self, dataset_id: str, name: str, base_model: str, epochs: int, image_size: int) -> dict:
        dataset = self.builder.get_dataset(dataset_id)
        health = self.builder.health(dataset_id)
        if health["train"] < 20 or health["validation"] < 5:
            raise DatasetError("Training requires at least 20 verified train and 5 verified validation images.")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name):
            raise DatasetError("Model name may contain only letters, numbers, dots, dashes, and underscores.")
        model_id, now = uuid.uuid4().hex, _now()
        output = self.builder.model_root / dataset["class_name"] / name / "best.pt"
        if output.exists() or self.builder.database.dataset_fetchone("SELECT id FROM vision_models WHERE name=?", (name,)):
            raise DatasetError("Model versions are immutable; choose a new model name.")
        output.parent.mkdir(parents=True, exist_ok=False)
        dataset_path = self.builder.materialize(dataset_id) / "dataset.yaml"
        log_path = output.parent / "training.log"
        config = {"epochs": epochs, "image_size": image_size, "log_path": str(log_path)}
        self.builder.database.dataset_execute(
            "INSERT INTO vision_models(id,dataset_id,name,base_model,weights_path,status,training_config,metrics,benchmark_accuracy,deployment_status,started_at,finished_at,deployed_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (model_id, dataset_id, name, base_model, str(output), "QUEUED", json.dumps(config), "{}", None, "NOT_DEPLOYED", None, None, None, now),
        )
        thread = threading.Thread(target=self._run, args=(model_id, dataset_path, base_model, epochs, image_size, output, log_path), daemon=True)
        thread.start()
        return self.model(model_id)

    def _run(self, model_id: str, dataset_path: Path, base_model: str, epochs: int,
             image_size: int, output: Path, log_path: Path) -> None:
        self.builder.database.dataset_execute("UPDATE vision_models SET status='TRAINING',started_at=? WHERE id=?", (_now(), model_id))
        command = [sys.executable, str(self.builder.root / "scripts" / "train_baget_detector.py"), "--data", str(dataset_path),
                   "--base-model", base_model, "--epochs", str(epochs), "--image-size", str(image_size), "--output", str(output)]
        try:
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command, cwd=self.builder.root, stdout=log, stderr=subprocess.STDOUT, text=True)
                with self._lock:
                    self._processes[model_id] = process
                return_code = process.wait()
            status = "COMPLETED" if return_code == 0 and output.exists() else "FAILED"
            metrics = {"return_code": return_code, "log_path": str(log_path)}
        except Exception as exc:  # noqa: BLE001
            status, metrics = "FAILED", {"error": str(exc), "log_path": str(log_path)}
        finally:
            with self._lock:
                self._processes.pop(model_id, None)
        self.builder.database.dataset_execute(
            "UPDATE vision_models SET status=?,metrics=?,finished_at=? WHERE id=?",
            (status, json.dumps(metrics), _now(), model_id),
        )

    def models(self) -> list[dict]:
        return [self._decode(row) for row in self.builder.database.dataset_fetchall("SELECT * FROM vision_models ORDER BY created_at DESC")]

    def model(self, model_id: str) -> dict:
        row = self.builder.database.dataset_fetchone("SELECT * FROM vision_models WHERE id=?", (model_id,))
        if row is None:
            raise DatasetError("Model not found.")
        return self._decode(row)

    @staticmethod
    def _decode(row: dict) -> dict:
        for key in ("training_config", "metrics"):
            try:
                row[key] = json.loads(row.get(key) or "{}")
            except json.JSONDecodeError:
                row[key] = {}
        return row
