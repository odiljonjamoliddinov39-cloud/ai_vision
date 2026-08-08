"""Recognition boundary between tracking observations and business rules."""
from __future__ import annotations

from dataclasses import dataclass

from recognition.product_recognizer import ProductRecognition, crop_image


@dataclass(frozen=True)
class RecognitionObservation:
    track_id: int | None
    detector_class: str
    identity: str
    confidence: float
    source: str
    known: bool


class RecognitionEngine:
    """Recognize every detection locally first; Gemini is unknown-only fallback."""

    GENERIC_IDENTITIES = {"", "object", "object proposal", "unknown", "unknown object"}

    def __init__(self, recognizer=None) -> None:
        self.recognizer = recognizer
        self._track_results: dict[tuple[str, int], RecognitionObservation] = {}

    def recognize(self, camera_id: str, frame, detections) -> list[RecognitionObservation]:
        if self.recognizer is not None:
            self.recognizer.poll()
        results = []
        for detection in detections:
            results.append(self._recognize_one(camera_id, frame, detection))
        return results

    def _recognize_one(self, camera_id: str, frame, detection) -> RecognitionObservation:
        track_id = getattr(detection, "track_id", None)
        detector_class = str(getattr(detection, "class_name", "object") or "object")
        key = (camera_id, int(track_id)) if track_id is not None else None
        if key is not None and key in self._track_results:
            result = self._track_results[key]
            self._apply(detection, result)
            return result

        provider_result = (
            self.recognizer.get_track_result(camera_id, int(track_id))
            if self.recognizer is not None and track_id is not None
            else None
        )
        if provider_result is not None and provider_result.name != "Unknown Product":
            result = self._result(track_id, detector_class, provider_result)
            if key is not None:
                self._track_results[key] = result
            self._apply(detection, result)
            return result

        # Cropping is needed only when a recognition provider can consume it.
        # Detector-native identities remain valid without an image copy.
        crop = crop_image(frame, detection.box) if self.recognizer is not None else None
        local = None
        if self.recognizer is not None and crop is not None:
            local = self.recognizer.recognize_local(crop)
        if local is not None and local.name != "Unknown Product":
            result = self._result(track_id, detector_class, local)
            if key is not None:
                self._track_results[key] = result
            self._apply(detection, result)
            return result

        detector_key = " ".join(detector_class.replace("_", " ").split()).casefold()
        if detector_key not in self.GENERIC_IDENTITIES:
            result = RecognitionObservation(
                track_id, detector_class, detector_class,
                float(getattr(detection, "confidence", 0.0)), "detector", True,
            )
            if key is not None:
                self._track_results[key] = result
            self._apply(detection, result)
            return result

        if self.recognizer is not None and key is not None and crop is not None:
            self.recognizer.submit_crop_for_track(camera_id, int(track_id), crop)
        result = RecognitionObservation(
            track_id, detector_class, "Unknown Product",
            float(getattr(detection, "confidence", 0.0)), "unknown_pending", False,
        )
        self._apply(detection, result)
        return result

    @staticmethod
    def _result(track_id, detector_class, product: ProductRecognition) -> RecognitionObservation:
        return RecognitionObservation(
            track_id, detector_class, product.name, float(product.confidence),
            product.source, True,
        )

    @staticmethod
    def _apply(detection, result: RecognitionObservation) -> None:
        detection.inventory_name = result.identity if result.known else None
        detection.recognition_source = result.source
        detection.recognition_confidence = result.confidence

    def reset(self, camera_id: str) -> None:
        self._track_results = {
            key: value for key, value in self._track_results.items() if key[0] != camera_id
        }
