"""Tests for fail-safe report/evidence consistency validation."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from src.validation.report_validator import validate_report


class ReportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = json.loads(Path("output/pader_report.json").read_text(encoding="utf-8"))
        self.evidence = json.loads(Path("data/evidence.json").read_text(encoding="utf-8"))

    def test_generated_report_passes_deterministic_validation(self) -> None:
        result = validate_report(self.report, self.evidence)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["numeric_claims_failed"], 0)

    def test_unsupported_number_blocks_finalization(self) -> None:
        altered = copy.deepcopy(self.report)
        altered["sections"][1]["generated_content"] += " A total of 9,999 cases were received."
        result = validate_report(altered, self.evidence)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["finalization_status"], "blocked_pending_human_review")
        self.assertTrue(any(issue["code"] == "unsupported_numeric_claim" for issue in result["errors"]))

    def test_missing_or_unknown_evidence_blocks_finalization(self) -> None:
        altered = copy.deepcopy(self.report)
        altered["sections"][0]["evidence_ids"] = []
        result = validate_report(altered, self.evidence)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["missing_evidence"])

    def test_unsupported_expectedness_claim_is_flagged(self) -> None:
        altered = copy.deepcopy(self.report)
        altered["sections"][3]["generated_content"] += " The reaction was expected."
        result = validate_report(altered, self.evidence)
        self.assertTrue(any(issue["code"] == "unsupported_expectedness_claim" for issue in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
