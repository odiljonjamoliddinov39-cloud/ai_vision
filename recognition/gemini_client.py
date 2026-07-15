"""Gemini Vision provider for product recognition."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Protocol

import cv2

from recognition.prompt_builder import build_product_prompt


class RecognitionProvider(Protocol):
    def recognize(self, image):
        ...


class GeminiClient:
    """Minimal REST client for Gemini Vision.

    The client uses the public Gemini REST endpoint directly so the project does
    not fail to import when the optional Google SDK is not installed.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.1-flash-lite",
        timeout: int = 30,
        retries: int = 2,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self.timeout = max(1, int(timeout))
        self.retries = max(0, int(retries))

    def recognize(self, image):
        from recognition.product_recognizer import ProductRecognition

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        payload = self._build_payload(image)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        encoded = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    data=encoded,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                product_json = _extract_json_text(response_payload)
                return ProductRecognition.from_provider_json(product_json)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except Exception as exc:  # noqa: BLE001 - provider errors must never crash detection.
                last_error = exc
            if attempt < self.retries:
                time.sleep(min(2**attempt, 4))
        raise RuntimeError(f"Gemini recognition failed: {last_error}")

    def _build_payload(self, image) -> dict:
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise ValueError("Could not encode crop for Gemini.")
        return {
            "contents": [
                {
                    "parts": [
                        {"text": build_product_prompt()},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64.b64encode(encoded.tobytes()).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }


def _extract_json_text(response_payload: dict) -> dict:
    candidates = response_payload.get("candidates") or []
    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts") or []
        for part in parts:
            text = part.get("text")
            if text:
                return _parse_json_object(text)
    raise ValueError("Gemini response did not contain JSON text.")


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Provider response was not a JSON object.")
    return json.loads(cleaned[start : end + 1])
