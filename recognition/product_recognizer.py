"""Asynchronous product recognition service."""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from knowledge.product_database import ProductDatabase
from recognition.cache import RecognitionCache
from recognition.embedding import image_embedding, image_hash
from recognition.gemini_client import GeminiClient

logger = logging.getLogger("product_recognition")


@dataclass
class ProductRecognition:
    id: int | None = None
    name: str = "Unknown Product"
    category: str | None = None
    brand: str | None = None
    material: str | None = None
    description: str | None = None
    color: str | None = None
    shape: str | None = None
    estimated_size: str | None = None
    possible_usage: str | None = None
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "unknown"

    @classmethod
    def from_provider_json(cls, payload: dict[str, Any]) -> "ProductRecognition":
        return cls(
            name=str(payload.get("name") or "Unknown Product"),
            category=_optional_str(payload.get("category")),
            brand=_optional_str(payload.get("brand")),
            material=_optional_str(payload.get("material")),
            description=_optional_str(payload.get("description")),
            color=_optional_str(payload.get("color")),
            shape=_optional_str(payload.get("shape")),
            estimated_size=_optional_str(payload.get("estimated_size")),
            possible_usage=_optional_str(payload.get("possible_usage")),
            confidence=_safe_confidence(payload.get("confidence")),
            source="gemini",
        )

    @classmethod
    def from_db(cls, payload: dict[str, Any], source: str = "local") -> "ProductRecognition":
        return cls(
            id=payload.get("id"),
            name=str(payload.get("name") or "Unknown Product"),
            category=_optional_str(payload.get("category")),
            brand=_optional_str(payload.get("brand")),
            material=_optional_str(payload.get("material")),
            description=_optional_str(payload.get("description")),
            color=_optional_str(payload.get("color")),
            shape=_optional_str(payload.get("shape")),
            estimated_size=_optional_str(payload.get("estimated_size")),
            possible_usage=_optional_str(payload.get("possible_usage")),
            confidence=_safe_confidence(payload.get("confidence")),
            created_at=str(payload.get("created_at") or datetime.utcnow().isoformat()),
            source=source,
        )

    @classmethod
    def unknown(cls, source: str = "error") -> "ProductRecognition":
        return cls(name="Unknown Product", confidence=0.0, source=source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "brand": self.brand,
            "material": self.material,
            "description": self.description,
            "color": self.color,
            "shape": self.shape,
            "estimated_size": self.estimated_size,
            "possible_usage": self.possible_usage,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "source": self.source,
        }


class ProductRecognizer:
    def __init__(
        self,
        provider=None,
        product_db: ProductDatabase | None = None,
        enabled: bool = True,
        confidence_threshold: float = 0.90,
        similarity_threshold: float = 0.92,
        cache_enabled: bool = True,
        cache_expiration: int = 1800,
        max_workers: int = 2,
    ):
        self.enabled = enabled
        self.provider = provider
        self.product_db = product_db or ProductDatabase()
        self.confidence_threshold = float(confidence_threshold)
        self.similarity_threshold = float(similarity_threshold)
        self.cache_enabled = cache_enabled
        self.cache = RecognitionCache(cache_expiration)
        self.executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)))
        self._pending: dict[tuple[str, int], Future] = {}
        self._results: dict[tuple[str, int], ProductRecognition] = {}
        self._track_hashes: dict[tuple[str, int], str] = {}

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ProductRecognizer | None":
        if not config.get("enabled", False):
            return None
        provider_name = config.get("provider", "gemini")
        provider = None
        if provider_name == "gemini":
            provider = GeminiClient(
                model=config.get("model", "gemini-3.1-flash-lite"),
                timeout=int(config.get("timeout", 30)),
                retries=int(config.get("retries", 2)),
            )
        else:
            raise ValueError(f"Unsupported recognition provider: {provider_name}")
        return cls(
            provider=provider,
            product_db=ProductDatabase(config.get("db_path", "database/products.db")),
            enabled=bool(config.get("enabled", True)),
            confidence_threshold=float(config.get("confidence_threshold", 0.90)),
            similarity_threshold=float(config.get("similarity_threshold", 0.92)),
            cache_enabled=bool(config.get("cache_enabled", True)),
            cache_expiration=int(config.get("cache_expiration", 1800)),
            max_workers=int(config.get("max_workers", 2)),
        )

    def submit_for_track(self, camera_name: str, track_id: int, frame, box, force_refresh: bool = False) -> None:
        if not self.enabled:
            return
        key = (camera_name, int(track_id))
        if key in self._results or key in self._pending:
            return
        crop = crop_image(frame, box)
        if crop is None:
            return
        future = self.executor.submit(self.recognize, crop.copy(), force_refresh)
        self._pending[key] = future

    def poll(self) -> None:
        for key, future in list(self._pending.items()):
            if not future.done():
                continue
            try:
                self._results[key] = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Product recognition future failed: %s", exc)
                self._results[key] = ProductRecognition.unknown()
            self._pending.pop(key, None)

    def get_track_result(self, camera_name: str, track_id: int) -> ProductRecognition | None:
        self.poll()
        return self._results.get((camera_name, int(track_id)))

    def annotate(self, camera_name: str, frame, detections) -> None:
        if not self.enabled:
            return
        self.poll()
        for detection in detections:
            track_id = getattr(detection, "track_id", None)
            if track_id is None:
                continue
            result = self.get_track_result(camera_name, int(track_id))
            if result is not None and result.name != "Unknown Product":
                detection.inventory_name = result.name
                continue
            crop = crop_image(frame, detection.box)
            if crop is None:
                continue
            local = self.recognize_local(crop)
            if local is not None and local.name != "Unknown Product":
                self._results[(camera_name, int(track_id))] = local
                detection.inventory_name = local.name
                continue
            self.submit_crop_for_track(camera_name, int(track_id), crop)

    def submit_crop_for_track(self, camera_name: str, track_id: int, crop, force_refresh: bool = False) -> None:
        key = (camera_name, int(track_id))
        if key in self._results or key in self._pending:
            return
        future = self.executor.submit(self.recognize, crop.copy(), force_refresh)
        self._pending[key] = future

    def recognize(self, image, force_refresh: bool = False) -> ProductRecognition:
        start = time.perf_counter()
        fingerprint = image_hash(image)
        embedding = image_embedding(image)

        if not force_refresh:
            local = self._recognize_local(fingerprint, embedding, start)
            if local is not None:
                return local

        if self.provider is None:
            result = ProductRecognition.unknown(source="no_provider")
            self._log_result(result, "no_provider", start)
            return result

        try:
            result = self.provider.recognize(image)
            if result.confidence < self.confidence_threshold:
                logger.info(
                    "Provider confidence %.3f below threshold %.3f for %s",
                    result.confidence,
                    self.confidence_threshold,
                    result.name,
                )
            saved = self.product_db.save_product(result, embedding, fingerprint)
            stored = ProductRecognition.from_db(saved, source=result.source or "gemini")
            self._cache(fingerprint, stored)
            self._log_result(stored, stored.source, start)
            return stored
        except Exception as exc:  # noqa: BLE001
            logger.warning("Provider recognition failed; returning unknown product: %s", exc)
            result = ProductRecognition.unknown()
            self._log_result(result, "error", start)
            return result

    def recognize_local(self, image) -> ProductRecognition | None:
        """Fast cache/knowledge lookup that never calls the provider."""
        start = time.perf_counter()
        fingerprint = image_hash(image)
        embedding = image_embedding(image)
        return self._recognize_local(fingerprint, embedding, start)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _cache(self, fingerprint: str, result: ProductRecognition) -> None:
        if self.cache_enabled:
            self.cache.set(fingerprint, result)

    def _recognize_local(
        self,
        fingerprint: str,
        embedding: list[float],
        start: float,
    ) -> ProductRecognition | None:
        if self.cache_enabled:
            cached = self.cache.get(fingerprint)
            if cached is not None:
                self._log_result(cached, "cache", start)
                return cached

        exact = self.product_db.get_by_hash(fingerprint)
        if exact:
            result = ProductRecognition.from_db(exact, source="local_hash")
            self._cache(fingerprint, result)
            self._log_result(result, "local_hash", start)
            return result

        similar = self.product_db.similar_products(embedding, limit=5)
        if similar and float(similar[0].get("similarity") or 0.0) >= self.similarity_threshold:
            result = ProductRecognition.from_db(similar[0], source="local_similarity")
            result.confidence = max(result.confidence, float(similar[0].get("similarity") or 0.0))
            self._cache(fingerprint, result)
            self._log_result(result, "local_similarity", start)
            return result
        return None

    def _log_result(self, result: ProductRecognition, source: str, start: float) -> None:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "product=%s source=%s latency_ms=%.1f confidence=%.3f",
            result.name,
            source,
            latency_ms,
            result.confidence,
        )


def crop_image(frame, box, padding: int = 8):
    if frame is None or box is None:
        return None
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = [int(value) for value in box]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(width, x2 + padding)
    y2 = min(height, y2 + padding)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return np.ascontiguousarray(crop)


def _optional_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
