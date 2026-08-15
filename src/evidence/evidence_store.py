"""Persistence and LLM-safe retrieval for approved evidence only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .claim_schema import validate_evidence_item


def save_evidence(document: dict[str, Any], path: str | Path) -> None:
    """Validate and persist an evidence document as UTF-8 JSON."""
    items = document.get("evidence_items")
    if not isinstance(items, list):
        raise ValueError("Evidence document must contain an evidence_items list.")
    seen: set[str] = set()
    for item in items:
        validate_evidence_item(item)
        if item["evidence_id"] in seen:
            raise ValueError(f"Duplicate evidence_id: {item['evidence_id']}")
        seen.add(item["evidence_id"])
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_evidence(path: str | Path) -> dict[str, Any]:
    """Load and validate an existing approved evidence document."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    for item in document.get("evidence_items", []):
        validate_evidence_item(item)
    return document


def llm_safe_context(document: dict[str, Any], evidence_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Return only approved evidence items; raw datasets are never accepted here."""
    items = document["evidence_items"]
    if evidence_ids is None:
        return items
    selected = [item for item in items if item["evidence_id"] in set(evidence_ids)]
    unknown = set(evidence_ids) - {item["evidence_id"] for item in selected}
    if unknown:
        raise KeyError(f"Unknown evidence IDs: {sorted(unknown)}")
    return selected
