"""Fast local image hashing and lightweight embeddings.

These helpers intentionally avoid cloud calls and heavy ML dependencies. They
are good enough for a first-pass warehouse knowledge cache: exact/similar crops
are reused locally, while truly unknown objects can still be escalated to a
vision provider such as Gemini.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

import cv2
import numpy as np


def image_hash(image) -> str:
    """Return a stable SHA-256 hash for a normalized crop image."""
    normalized = _normalized_image(image, size=(96, 96))
    ok, encoded = cv2.imencode(".jpg", normalized, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    data = encoded.tobytes() if ok else normalized.tobytes()
    return hashlib.sha256(data).hexdigest()


def image_embedding(image, bins: int = 8) -> list[float]:
    """Build a compact color/shape embedding for similarity search."""
    normalized = _normalized_image(image, size=(96, 96))
    hsv = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [bins, bins, bins], [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()

    gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    aspect_hint = float(normalized.shape[1] / max(1, normalized.shape[0]))

    vector = np.concatenate([hist.astype("float32"), np.array([edge_density, aspect_hint], dtype="float32")])
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm
    return [float(v) for v in vector]


def serialize_embedding(values: Iterable[float]) -> str:
    return json.dumps([round(float(value), 8) for value in values], separators=(",", ":"))


def deserialize_embedding(value: str | bytes | None) -> list[float]:
    if not value:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [float(item) for item in loaded if isinstance(item, int | float)]


def _normalized_image(image, size: tuple[int, int]):
    if image is None or getattr(image, "size", 0) == 0:
        return np.zeros((size[1], size[0], 3), dtype=np.uint8)
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)
