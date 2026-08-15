"""Schema and validation for deterministic evidence claims."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


REQUIRED_KEYS = {
    "evidence_id", "metric", "value", "unit", "analysis_name", "source_fields",
    "calculation", "filters", "case_level_or_reaction_level", "limitations",
}


@dataclass(frozen=True)
class EvidenceItem:
    """A claim-ready value derived from an approved deterministic analysis metric."""

    evidence_id: str
    metric: str
    value: Any
    unit: str
    analysis_name: str
    source_fields: list[str]
    calculation: str
    filters: list[str]
    case_level_or_reaction_level: str
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_evidence_item(item: dict[str, Any]) -> None:
    """Fail fast if an item is incomplete or not explicitly analysis-derived."""
    missing = REQUIRED_KEYS - set(item)
    if missing:
        raise ValueError(f"Evidence item missing required keys: {sorted(missing)}")
    if not isinstance(item["evidence_id"], str) or not item["evidence_id"].startswith("EV-"):
        raise ValueError("evidence_id must be a string beginning with 'EV-'.")
    if item["case_level_or_reaction_level"] not in {"case", "reaction", "report", "mixed"}:
        raise ValueError("case_level_or_reaction_level must be case, reaction, report, or mixed.")
    for field in ("source_fields", "filters", "limitations"):
        if not isinstance(item[field], list):
            raise ValueError(f"{field} must be a list.")
    if not item["calculation"]:
        raise ValueError("calculation must document deterministic provenance.")
