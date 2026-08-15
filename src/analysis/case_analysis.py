"""Case-level analysis helpers and summary metrics."""
from __future__ import annotations

from typing import Any

import pandas as pd


CASE_ID = "safetyreportid"


def metric(value: Any, *, unit: str, calculation: str, source_fields: list[str], level: str) -> dict[str, Any]:
    """Return a JSON-serializable metric with traceability metadata."""
    return {
        "value": value,
        "unit": unit,
        "calculation": calculation,
        "source_fields": source_fields,
        "analysis_level": level,
    }


def case_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Create one reproducible representative row per non-missing case ID.

    The first source-row order is retained deliberately. This is used only for
    case-level fields; reaction rows are never removed from reaction analyses.
    Validation separately flags conflicting case-level values across source rows.
    """
    valid_ids = frame[CASE_ID].notna() & frame[CASE_ID].astype("string").str.strip().ne("")
    return frame.loc[valid_ids].drop_duplicates(subset=[CASE_ID], keep="first").copy()


def analyze_cases(frame: pd.DataFrame) -> dict[str, Any]:
    cases = case_frame(frame)
    serious = cases["normalized_serious"].eq("serious")
    non_serious = cases["normalized_serious"].eq("not_serious")
    total = int(len(cases))
    serious_count = int(serious.sum())
    return {
        "total_cases": metric(total, unit="cases", calculation="nunique(safetyreportid)", source_fields=[CASE_ID], level="case"),
        "serious_cases": metric(serious_count, unit="cases", calculation="case_frame().normalized_serious.eq('serious').sum()", source_fields=[CASE_ID, "normalized_serious", "raw_serious"], level="case"),
        "non_serious_cases": metric(int(non_serious.sum()), unit="cases", calculation="case_frame().normalized_serious.eq('not_serious').sum()", source_fields=[CASE_ID, "normalized_serious", "raw_serious"], level="case"),
        "serious_case_percentage": metric(round(100 * serious_count / total, 2) if total else None, unit="percent", calculation="100 * serious_cases / total_cases", source_fields=[CASE_ID, "normalized_serious"], level="case"),
        "case_representative_row_policy": "First source-row order per non-missing safetyreportid; only for case-level metrics. Reaction-level analyses use all source rows.",
    }
