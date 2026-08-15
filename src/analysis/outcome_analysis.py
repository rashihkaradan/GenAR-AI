"""Reaction-outcome distribution analysis."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .case_analysis import metric


OUTCOME_FIELD = "normalized_outcome"


def outcome_instances(frame: pd.DataFrame) -> pd.Series:
    values = frame[OUTCOME_FIELD].dropna().astype("string").str.split(",").explode().str.strip()
    return values[values.ne("")]


def analyze_outcomes(frame: pd.DataFrame) -> dict[str, Any]:
    values = outcome_instances(frame)
    counts = values.value_counts()
    return {
        "outcome_count": metric(int(len(values)), unit="reaction_outcome_instances", calculation="count of non-empty comma-split normalized outcomes across source rows", source_fields=[OUTCOME_FIELD, "raw_patient_reaction_reactionoutcome"], level="reaction"),
        "outcome_distribution": metric([{"outcome": str(value), "count": int(count)} for value, count in counts.items()], unit="reaction_outcome_instances", calculation="comma_split(normalized_outcome).value_counts(); no deduplication", source_fields=[OUTCOME_FIELD, "raw_patient_reaction_reactionoutcome"], level="reaction"),
    }
