"""Tests for the deterministic analysis-to-evidence boundary."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.evidence.evidence_builder import GLOBAL_LIMITATIONS, build_evidence
from src.evidence.evidence_store import llm_safe_context, load_evidence


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        self.evidence = build_evidence(self.analysis)

    def test_evidence_is_derived_from_analysis_values(self) -> None:
        total = next(item for item in self.evidence["evidence_items"] if item["evidence_id"] == "EV-CASE-001")
        self.assertEqual(total["value"], self.analysis["case_summary"]["total_cases"]["value"])
        self.assertEqual(total["calculation"], "nunique(safetyreportid)")
        self.assertEqual(total["case_level_or_reaction_level"], "case")

    def test_required_limitations_are_explicit(self) -> None:
        limitations = next(item for item in self.evidence["evidence_items"] if item["evidence_id"] == "EV-LIMIT-001")
        self.assertEqual(limitations["value"], GLOBAL_LIMITATIONS)
        self.assertEqual(len(limitations["value"]), 5)

    def test_llm_context_returns_only_requested_approved_items(self) -> None:
        selected = llm_safe_context(self.evidence, ["EV-CASE-001", "EV-REACT-001"])
        self.assertEqual([item["evidence_id"] for item in selected], ["EV-CASE-001", "EV-REACT-001"])

    def test_written_evidence_validates(self) -> None:
        path = Path("data/evidence.json")
        self.assertTrue(path.exists(), "Run evidence builder before integration test.")
        document = load_evidence(path)
        self.assertGreaterEqual(len(document["evidence_items"]), 20)


if __name__ == "__main__":
    unittest.main()
