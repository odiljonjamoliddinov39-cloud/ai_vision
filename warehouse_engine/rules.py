from __future__ import annotations


class RuleEngine:
    def __init__(self, minimum_confidence: float = 0.8):
        self.minimum_confidence = float(minimum_confidence)
        self.applied: set[tuple[str, str]] = set()

    def inventory_delta(
        self,
        object_id: str,
        confidence: float,
        crossing: str | None,
    ) -> tuple[int, str]:
        if confidence < self.minimum_confidence:
            return 0, "low_confidence"
        if crossing not in {"IN", "OUT"}:
            return 0, "no_inventory_rule"
        key = (object_id, crossing)
        if key in self.applied:
            return 0, "duplicate_ignored"
        self.applied.add(key)
        return (1 if crossing == "IN" else -1), "line_crossing"


def parse_task_prompt(prompt: str) -> dict:
    """Deterministic task-builder baseline; an LLM can replace this parser."""
    text = " ".join(prompt.lower().split())
    target = text
    for prefix in ("count all ", "count ", "track all ", "track "):
        if target.startswith(prefix):
            target = target[len(prefix):]
            break
    for suffix in (" entering warehouse", " leaving warehouse", " in warehouse"):
        target = target.replace(suffix, "")
    return {
        "target_object": target.strip(" .") or "object",
        "zone": "Receiving" if "enter" in text else "Shipping" if "leav" in text else "Any",
        "action": "count" if "count" in text else "track",
        "count_rule": "line_crossing",
        "minimum_confidence": 0.85,
        "duplicate_timeout": "60s",
        "tracking": "persistent",
    }
