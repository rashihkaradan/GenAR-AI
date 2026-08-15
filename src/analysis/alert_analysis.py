"""Expedited/alert case analysis based solely on the supplied alert criterion."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .case_analysis import case_frame, metric
from .outcome_analysis import outcome_instances
from .reaction_analysis import reaction_instances


def _case_distribution(cases: pd.DataFrame, field: str) -> list[dict[str, Any]]:
    values = cases[field].fillna("missing").astype("string").value_counts()
    return [{"category": str(value), "count": int(count)} for value, count in values.items()]


def analyze_alerts(frame: pd.DataFrame, *, top_n: int = 20) -> dict[str, Any]:
    alert_rows = frame.loc[frame["normalized_expedited"].eq("yes")]
    alert_cases = case_frame(alert_rows)
    serious = alert_cases["normalized_serious"].eq("serious")
    non_serious = alert_cases["normalized_serious"].eq("not_serious")
    # A case is "fatal recorded" only when any of its supplied reaction outcomes is fatal.
    fatal_ids = set(
        alert_rows.loc[alert_rows["normalized_outcome"].fillna("").astype("string").str.split(",").apply(lambda x: "fatal" in [term.strip() for term in x]), "safetyreportid"].dropna()
    )
    reaction_counts = reaction_instances(alert_rows).value_counts()
    outcome_counts = outcome_instances(alert_rows).value_counts()
    total = int(len(alert_cases))
    fatal = int(alert_cases["safetyreportid"].isin(fatal_ids).sum())
    return {
        "alert_cases": metric(total, unit="cases", calculation="nunique(safetyreportid) where normalized_expedited == 'yes'", source_fields=["safetyreportid", "normalized_expedited", "raw_fulfillexpeditecriteria"], level="case"),
        "serious_non_serious_distribution": metric([{"category": "serious", "count": int(serious.sum())}, {"category": "not_serious", "count": int(non_serious.sum())}], unit="cases", calculation="case_frame(alert_rows).normalized_serious value counts", source_fields=["safetyreportid", "normalized_expedited", "normalized_serious"], level="case"),
        "fatal_outcome_recorded_cases": metric(fatal, unit="cases", calculation="nunique alert safetyreportid with any comma-split normalized_outcome == 'fatal'", source_fields=["safetyreportid", "normalized_expedited", "normalized_outcome"], level="case"),
        "cases_without_recorded_fatal_outcome": metric(total - fatal, unit="cases", calculation="alert_cases - fatal_outcome_recorded_cases; does not establish non-fatal status", source_fields=["safetyreportid", "normalized_expedited", "normalized_outcome"], level="case"),
        "reaction_distribution": metric([{"reaction": str(term), "count": int(count)} for term, count in reaction_counts.items()], unit="reaction_instances", calculation="alert source rows only; comma_split(PT).value_counts(); no deduplication", source_fields=["normalized_expedited", "patient_reaction_reactionmeddrapt"], level="reaction"),
        "top_reactions": metric([{"reaction": str(term), "count": int(count)} for term, count in reaction_counts.head(top_n).items()], unit="reaction_instances", calculation=f"alert reaction distribution sorted descending; first {top_n}", source_fields=["normalized_expedited", "patient_reaction_reactionmeddrapt"], level="reaction"),
        "outcome_distribution": metric([{"outcome": str(value), "count": int(count)} for value, count in outcome_counts.items()], unit="reaction_outcome_instances", calculation="alert source rows only; comma_split(normalized_outcome).value_counts(); no deduplication", source_fields=["normalized_expedited", "normalized_outcome"], level="reaction"),
        "country_distribution": metric(_case_distribution(alert_cases, "normalized_country"), unit="cases", calculation="case_frame(alert_rows).normalized_country.fillna('missing').value_counts()", source_fields=["safetyreportid", "normalized_expedited", "normalized_country", "raw_occurcountry"], level="case"),
        "scope_note": "Alert status is the supplied expedited criterion only; expectedness is not inferred.",
    }
