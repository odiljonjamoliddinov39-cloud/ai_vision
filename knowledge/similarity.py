"""Similarity helpers for local product knowledge lookup."""

from __future__ import annotations

import math


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(dot / (left_norm * right_norm))


def top_matches(query: list[float], candidates: list[dict], limit: int = 5) -> list[dict]:
    ranked = []
    for candidate in candidates:
        score = cosine_similarity(query, candidate.get("embedding") or [])
        ranked.append({**candidate, "similarity": score})
    return sorted(ranked, key=lambda item: item["similarity"], reverse=True)[:limit]
