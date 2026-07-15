from __future__ import annotations

import time

import numpy as np

from knowledge.product_database import ProductDatabase
from knowledge.similarity import cosine_similarity
from recognition.embedding import image_embedding, image_hash
from recognition.product_recognizer import (
    ProductRecognition,
    ProductRecognizer,
    _normalize_gemini_model,
    crop_image,
)


class FakeProvider:
    def __init__(self, name: str = "Blue Box"):
        self.name = name
        self.calls = 0

    def recognize(self, image):
        self.calls += 1
        return ProductRecognition(
            name=self.name,
            category="packaging",
            material="cardboard",
            color="blue",
            shape="cuboid",
            confidence=0.96,
            source="gemini",
        )


class FailingProvider:
    def recognize(self, image):
        raise RuntimeError("provider down")


def _image(color=(255, 0, 0)):
    img = np.zeros((80, 100, 3), dtype=np.uint8)
    img[:, :] = color
    return img


def test_gemini_called_once_then_cache_reused(tmp_path):
    provider = FakeProvider()
    recognizer = ProductRecognizer(
        provider=provider,
        product_db=ProductDatabase(str(tmp_path / "products.db")),
        cache_enabled=True,
    )
    image = _image()

    first = recognizer.recognize(image)
    second = recognizer.recognize(image)

    assert first.name == "Blue Box"
    assert second.name == "Blue Box"
    assert provider.calls == 1


def test_local_hash_reuse_skips_provider_after_restart(tmp_path):
    db_path = str(tmp_path / "products.db")
    provider = FakeProvider("Known Carton")
    first = ProductRecognizer(provider=provider, product_db=ProductDatabase(db_path))
    image = _image()

    first.recognize(image)
    second = ProductRecognizer(
        provider=FakeProvider("Should Not Be Called"),
        product_db=ProductDatabase(db_path),
        cache_enabled=False,
    )
    result = second.recognize(image)

    assert result.name == "Known Carton"
    assert result.source == "local_hash"


def test_similarity_reuse_skips_provider_for_near_match(tmp_path):
    db_path = str(tmp_path / "products.db")
    base = _image((10, 80, 220))
    near = _image((11, 81, 219))
    first_provider = FakeProvider("Blue Warehouse Carton")
    first = ProductRecognizer(provider=first_provider, product_db=ProductDatabase(db_path))
    first.recognize(base)

    second_provider = FakeProvider("Should Not Be Called")
    second = ProductRecognizer(
        provider=second_provider,
        product_db=ProductDatabase(db_path),
        cache_enabled=False,
        similarity_threshold=0.90,
    )
    result = second.recognize(near)

    assert result.name == "Blue Warehouse Carton"
    assert result.source == "local_similarity"
    assert second_provider.calls == 0


def test_provider_failure_returns_unknown_without_crashing(tmp_path):
    recognizer = ProductRecognizer(
        provider=FailingProvider(),
        product_db=ProductDatabase(str(tmp_path / "products.db")),
        cache_enabled=False,
    )

    result = recognizer.recognize(_image())

    assert result.name == "Unknown Product"
    assert result.source == "error"


def test_unavailable_gemini_models_are_normalized():
    assert _normalize_gemini_model("gemini-1.5-flash") == "gemini-3.1-flash-lite"
    assert _normalize_gemini_model("models/gemini-2.5-flash") == "gemini-3.1-flash-lite"
    assert _normalize_gemini_model("models/gemini-3.1-flash-lite") == "gemini-3.1-flash-lite"


def test_async_annotate_does_not_block_and_sets_inventory_name(tmp_path):
    recognizer = ProductRecognizer(
        provider=FakeProvider("Async Box"),
        product_db=ProductDatabase(str(tmp_path / "products.db")),
        cache_enabled=False,
    )
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[50:130, 60:150] = (20, 120, 200)

    class Obj:
        track_id = 7
        class_name = "box"
        confidence = 0.95
        box = (60, 50, 150, 130)
        inventory_name = None

    obj = Obj()
    start = time.perf_counter()
    recognizer.annotate("Camera 1", frame, [obj])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2

    for _ in range(20):
        recognizer.annotate("Camera 1", frame, [obj])
        if obj.inventory_name == "Async Box":
            break
        time.sleep(0.05)

    assert obj.inventory_name == "Async Box"


def test_crop_and_embedding_helpers_are_stable():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:50, 20:70] = (50, 100, 150)
    crop = crop_image(frame, (20, 10, 70, 50), padding=0)

    assert crop.shape[:2] == (40, 50)
    assert image_hash(crop) == image_hash(crop.copy())
    assert cosine_similarity(image_embedding(crop), image_embedding(crop.copy())) > 0.99
