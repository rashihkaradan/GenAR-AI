"""Tests for deterministic case- and reaction-level analysis."""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.analysis.analysis_runner import analyze, load_normalized_cases
from src.ingestion.normalizer import normalize_dataframe


def analysis_frame() -> pd.DataFrame:
    source = pd.DataFrame({
        "safetyreportid": ["A1", "A1", "B2"],
        "receivedate": ["20250110", "20250110", "20250205"],
        "patient_patientonsetage": ["70", "70", "12"],
        "patient_patientonsetageunit": ["year", "year", "year"],
        "patient_patientsex": ["female", "female", "male"],
        "occurcountry": ["Italy", "Italy", "France"],
        "serious": ["serious", "serious", "not serious"],
        "patient_reaction_reactionmeddrapt": ["Nausea,Fatigue", "Headache", "Dizziness"],
        "patient_reaction_reactionoutcome": ["fatal,recovered/resolved", "unknown", "recovering/resolving"],
        "fulfillexpeditecriteria": ["yes", "yes", "no"],
    }, dtype="string")
    return normalize_dataframe(source)


class AnalysisTests(unittest.TestCase):
    def test_case_and_reaction_levels_are_distinct(self) -> None:
        results = analyze(analysis_frame())
        summary = results["case_summary"]
        self.assertEqual(summary["total_cases"]["value"], 2)
        self.assertEqual(summary["serious_cases"]["value"], 1)
        self.assertEqual(summary["non_serious_cases"]["value"], 1)
        self.assertEqual(results["reactions"]["reaction_count"]["value"], 4)
        self.assertEqual(results["reactions"]["serious_reaction_count"]["value"], 3)

    def test_alert_fatal_outcomes_and_trends_are_deterministic(self) -> None:
        results = analyze(analysis_frame())
        self.assertEqual(results["alerts"]["alert_cases"]["value"], 1)
        self.assertEqual(results["alerts"]["fatal_outcome_recorded_cases"]["value"], 1)
        self.assertEqual(results["alerts"]["cases_without_recorded_fatal_outcome"]["value"], 0)
        self.assertEqual(results["trends"]["cases_by_month"]["value"], [{"month": "2025-01", "count": 1}, {"month": "2025-02", "count": 1}])

    def test_actual_dataset_baseline_is_calculated_not_hardcoded(self) -> None:
        path = Path("data/normalized_cases.jsonl")
        self.assertTrue(path.exists(), "Run ingestion before executing integration analysis test.")
        results = analyze(load_normalized_cases(path))
        self.assertEqual(results["case_summary"]["total_cases"]["value"], 1024)
        self.assertEqual(results["case_summary"]["serious_cases"]["value"], 1023)
        self.assertEqual(results["case_summary"]["non_serious_cases"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
