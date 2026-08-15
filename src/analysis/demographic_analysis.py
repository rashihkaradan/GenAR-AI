"""Case-level demographic distributions."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .case_analysis import case_frame, metric


def _distribution(cases: pd.DataFrame, field: str, raw_field: str, label: str) -> dict[str, Any]:
    values = cases[field].fillna("missing").astype("string").value_counts(dropna=False)
    rows = [{"category": str(value), "count": int(count)} for value, count in values.items()]
    return metric(rows, unit="cases", calculation=f"case_frame()[{field!r}].fillna('missing').value_counts()", source_fields=["safetyreportid", field, raw_field], level="case") | {"description": label}


def analyze_demographics(frame: pd.DataFrame) -> dict[str, Any]:
    cases = case_frame(frame)
    return {
        "age_group_distribution": _distribution(cases, "age_group", "raw_patient_patientonsetage", "Deterministic age group distribution; unknown or nonstandard age/unit remains missing."),
        "sex_distribution": _distribution(cases, "normalized_sex", "raw_patient_patientsex", "Normalized supplied sex values."),
        "country_distribution": _distribution(cases, "normalized_country", "raw_occurcountry", "Occurrence-country distribution; only case/whitespace normalization is applied."),
    }
