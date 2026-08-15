"""Reaction-level MedDRA Preferred Term analysis with no SOC inference."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .case_analysis import metric


REACTION_FIELD = "patient_reaction_reactionmeddrapt"


def reaction_instances(frame: pd.DataFrame) -> pd.Series:
    """Return every non-empty comma-delimited PT instance, preserving repeats."""
    values = frame[REACTION_FIELD].dropna().astype("string").str.split(",").explode().str.strip()
    return values[values.ne("")]


def _distribution(values: pd.Series, *, source_fields: list[str], calculation: str) -> dict[str, Any]:
    counts = values.value_counts()
    rows = [{"reaction": str(term), "count": int(count)} for term, count in counts.items()]
    return metric(rows, unit="reaction_instances", calculation=calculation, source_fields=source_fields, level="reaction")


def analyze_reactions(frame: pd.DataFrame, *, top_n: int = 20) -> dict[str, Any]:
    all_instances = reaction_instances(frame)
    serious_instances = reaction_instances(frame.loc[frame["normalized_serious"].eq("serious")])
    all_distribution = _distribution(all_instances, source_fields=[REACTION_FIELD], calculation="comma_split(patient_reaction_reactionmeddrapt).value_counts(); no deduplication")
    serious_distribution = _distribution(serious_instances, source_fields=[REACTION_FIELD, "normalized_serious"], calculation="filter normalized_serious == 'serious', then comma_split(PT).value_counts(); no deduplication")
    return {
        "reaction_count": metric(int(len(all_instances)), unit="reaction_instances", calculation="count of non-empty comma-split Preferred Term instances across all source rows", source_fields=[REACTION_FIELD], level="reaction"),
        "reaction_counts": all_distribution,
        "most_frequently_reported_reactions": metric(all_distribution["value"][:top_n], unit="reaction_instances", calculation=f"reaction_counts sorted descending; first {top_n}", source_fields=[REACTION_FIELD], level="reaction"),
        "serious_reaction_count": metric(int(len(serious_instances)), unit="reaction_instances", calculation="count of comma-split Preferred Term instances where source row normalized_serious == 'serious'", source_fields=[REACTION_FIELD, "normalized_serious"], level="reaction"),
        "serious_reaction_counts": serious_distribution,
        "most_frequently_reported_serious_reactions": metric(serious_distribution["value"][:top_n], unit="reaction_instances", calculation=f"serious_reaction_counts sorted descending; first {top_n}", source_fields=[REACTION_FIELD, "normalized_serious"], level="reaction"),
        "scope_note": "Preferred Term only. No System Organ Class is inferred because no SOC field is supplied.",
    }
