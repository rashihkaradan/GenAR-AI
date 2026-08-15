"""Minimal, section-specific context packets built only from approved evidence."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evidence.evidence_store import load_evidence, llm_safe_context


SECTION_EVIDENCE_IDS: dict[str, list[str]] = {
    "narrative_summary": ["EV-PERIOD-001", "EV-CASE-001", "EV-CASE-002", "EV-CASE-003", "EV-CASE-004", "EV-REACT-001", "EV-OUTCOME-001", "EV-ALERT-001", "EV-LIMIT-001"],
    "case_analysis": ["EV-PERIOD-001", "EV-CASE-001", "EV-CASE-002", "EV-CASE-003", "EV-CASE-004", "EV-DEMO-001", "EV-DEMO-002", "EV-DEMO-003", "EV-LIMIT-001"],
    "reaction_analysis": ["EV-REACT-001", "EV-REACT-002", "EV-DEMO-001", "EV-DEMO-002", "EV-LIMIT-001"],
    "alert_analysis": ["EV-PERIOD-001", "EV-ALERT-001", "EV-ALERT-002", "EV-ALERT-003", "EV-ALERT-007", "EV-ALERT-005", "EV-ALERT-006", "EV-LIMIT-001"],
    "trends": ["EV-PERIOD-001", "EV-TREND-001", "EV-TREND-002", "EV-TREND-003", "EV-LIMIT-001"],
    "limitations": ["EV-LIMIT-001"],
}


@dataclass(frozen=True)
class SectionEvidencePacket:
    section: str
    evidence_ids: list[str]
    evidence_items: list[dict[str, Any]]

    def to_prompt_json(self) -> str:
        """Serialize approved evidence alone; raw records are deliberately absent."""
        return json.dumps({"section": self.section, "allowed_evidence_ids": self.evidence_ids, "evidence": self.evidence_items}, indent=2, ensure_ascii=False)


class ContextBuilder:
    """Build approved packets without exposing datasets to the LLM layer."""

    def __init__(self, evidence_document: dict[str, Any]) -> None:
        self._evidence_document = evidence_document

    @classmethod
    def from_paths(cls, evidence_path: str | Path = "data/evidence.json", analysis_path: str | Path | None = "data/analysis_results.json") -> "ContextBuilder":
        document = load_evidence(evidence_path)
        # Verify evidence was made from the supplied approved analysis. The analysis is
        # used only for integrity validation and is never placed in a model packet.
        if analysis_path is not None:
            analysis = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
            actual_hash = hashlib.sha256(json.dumps(analysis, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            if document.get("analysis_sha256") != actual_hash:
                raise ValueError("Evidence does not match the supplied analysis_results.json; rebuild evidence before generation.")
        return cls(document)

    def build(self, section: str) -> SectionEvidencePacket:
        if section not in SECTION_EVIDENCE_IDS:
            raise ValueError(f"Unsupported report section: {section}. Allowed: {sorted(SECTION_EVIDENCE_IDS)}")
        ids = SECTION_EVIDENCE_IDS[section]
        return SectionEvidencePacket(section=section, evidence_ids=ids, evidence_items=llm_safe_context(self._evidence_document, ids))
