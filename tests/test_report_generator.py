"""Tests for evidence-grounded complete report generation."""
from __future__ import annotations

import unittest

from src.reporting.report_generator import generate_report


class ReportGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = generate_report()
        self.sections = {item["section_name"]: item for item in self.report["sections"]}

    def test_all_required_sections_have_evidence_and_provenance(self) -> None:
        self.assertEqual(len(self.report["sections"]), 9)
        for section in self.report["sections"]:
            self.assertTrue(section["evidence_ids"])
            self.assertTrue(section["generation_timestamp"])
            self.assertTrue(section["model_name"])
            self.assertEqual(section["prompt_version"], "1.0.0")

    def test_case_index_is_reaction_row_listing(self) -> None:
        listing = self.sections["Case Index / Listing"]["generated_content"]
        self.assertEqual(len(listing), 1068)
        self.assertEqual(listing[0]["case_id"], "24780403")
        self.assertIn("reaction_preferred_terms", listing[0])

    def test_no_action_information_statement_is_explicit(self) -> None:
        content = self.sections["History of Actions"]["generated_content"].lower()
        self.assertIn("no history-of-actions information was supplied", content)


if __name__ == "__main__":
    unittest.main()
