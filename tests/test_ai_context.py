"""Tests for minimal evidence packets and model-output provenance enforcement."""
from __future__ import annotations

import unittest

from src.ai.context_builder import ContextBuilder, SECTION_EVIDENCE_IDS
from src.ai.generator import SectionGenerator
from src.ai.model_client import StaticModelClient


class AIContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ContextBuilder.from_paths()

    def test_packet_is_section_specific_and_contains_no_raw_records(self) -> None:
        packet = self.builder.build("reaction_analysis")
        self.assertEqual(packet.evidence_ids, SECTION_EVIDENCE_IDS["reaction_analysis"])
        rendered = packet.to_prompt_json()
        self.assertNotIn("24780403", rendered)  # no source case record is exposed
        self.assertNotIn("normalized_cases", rendered)
        self.assertEqual(len(packet.evidence_items), len(packet.evidence_ids))

    def test_generator_accepts_authorized_evidence_ids(self) -> None:
        client = StaticModelClient({"section": "narrative_summary", "content": "During the reporting period, 1,024 cases were received.", "evidence_ids": ["EV-PERIOD-001", "EV-CASE-001"]})
        generated = SectionGenerator(self.builder, client).generate("narrative_summary")
        self.assertEqual(generated.evidence_ids, ["EV-PERIOD-001", "EV-CASE-001"])

    def test_generator_rejects_invented_evidence_id(self) -> None:
        client = StaticModelClient({"section": "limitations", "content": "No SOC field was supplied.", "evidence_ids": ["EV-NOT-REAL"]})
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            SectionGenerator(self.builder, client).generate("limitations")


if __name__ == "__main__":
    unittest.main()
