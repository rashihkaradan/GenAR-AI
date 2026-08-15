"""Regression tests for deterministic ingestion validation and normalization."""
from __future__ import annotations

import unittest

import pandas as pd

from src.ingestion.normalizer import derive_age_group, normalize_dataframe
from src.ingestion.validator import validate_dataframe


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "safetyreportid": ["A1", "A1", "B2"],
        "receivedate": ["20250101", "20250101", "20250201"],
        "patient_patientonsetage": ["67", "67", "12"],
        "patient_patientonsetageunit": ["year", "year", "year"],
        "patient_patientsex": ["Female", "Female", "male"],
        "occurcountry": [" United Kingdom ", " United Kingdom ", "ITALY"],
        "serious": ["serious", "serious", "not serious"],
        "patient_reaction_reactionmeddrapt": ["Fatigue", "Hypotension", "Headache"],
        "patient_reaction_reactionoutcome": ["recovered/resolved", "unknown", "fatal"],
        "fulfillexpeditecriteria": ["yes", "yes", "no"],
    }, dtype="string")


class ValidationTests(unittest.TestCase):
    def test_multiple_reaction_rows_are_valid_and_not_deduplicated(self) -> None:
        result = validate_dataframe(valid_frame())
        self.assertEqual(result.report["input_rows"], 3)
        self.assertEqual(result.report["valid_rows"], 3)
        self.assertEqual(result.report["unique_cases"], 2)

    def test_missing_id_invalid_date_and_missing_reaction_are_invalid_rows(self) -> None:
        frame = valid_frame()
        frame.loc[0, "safetyreportid"] = pd.NA
        frame.loc[1, "receivedate"] = "20251340"
        frame.loc[2, "patient_reaction_reactionmeddrapt"] = ""
        result = validate_dataframe(frame)
        self.assertEqual(result.report["invalid_rows"], 3)
        self.assertFalse(result.row_valid.any())

    def test_normalizer_preserves_reaction_and_adds_deterministic_fields(self) -> None:
        frame = valid_frame()
        normalized = normalize_dataframe(frame)
        self.assertEqual(normalized["patient_reaction_reactionmeddrapt"].tolist(), frame["patient_reaction_reactionmeddrapt"].tolist())
        self.assertEqual(normalized["normalized_sex"].tolist(), ["female", "female", "male"])
        self.assertEqual(normalized["normalized_country"].tolist(), ["united kingdom", "united kingdom", "italy"])
        self.assertEqual(normalized["normalized_serious"].tolist(), ["serious", "serious", "not_serious"])
        self.assertEqual(normalized["age_group"].tolist(), ["65+ years", "65+ years", "12-17 years"])
        self.assertEqual(normalized["reporting_month"].tolist(), ["2025-01", "2025-01", "2025-02"])

    def test_unknown_age_unit_is_not_assumed(self) -> None:
        frame = valid_frame().iloc[[0]].copy()
        frame.loc[0, "patient_patientonsetageunit"] = "800"
        normalized = normalize_dataframe(frame)
        self.assertTrue(pd.isna(normalized.loc[0, "normalized_age_years"]))
        self.assertTrue(pd.isna(normalized.loc[0, "age_group"]))
        warning_codes = {warning["code"] for warning in validate_dataframe(frame).report["warnings"]}
        self.assertIn("unexpected_age_unit", warning_codes)

    def test_unexpected_categorical_value_is_reported_not_replaced(self) -> None:
        frame = valid_frame().iloc[[0]].copy()
        frame.loc[0, "patient_patientsex"] = "not-recorded-value"
        result = validate_dataframe(frame)
        warning = next(item for item in result.report["warnings"] if item.get("column") == "patient_patientsex")
        self.assertEqual(warning["values"], ["not-recorded-value"])
        self.assertEqual(normalize_dataframe(frame).loc[0, "normalized_sex"], "not-recorded-value")

    def test_age_group_boundaries(self) -> None:
        ages = pd.Series([0.0, 1.99, 2.0, 11.99, 12.0, 17.99, 18.0, 64.99, 65.0, 130.0], dtype="Float64")
        self.assertEqual(derive_age_group(ages).tolist(), ["0-1 years", "0-1 years", "2-11 years", "2-11 years", "12-17 years", "12-17 years", "18-64 years", "18-64 years", "65+ years", "65+ years"])


if __name__ == "__main__":
    unittest.main()
