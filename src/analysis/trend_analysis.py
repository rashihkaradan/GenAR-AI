"""Observed numerical patterns by reporting month; no safety-signal inference."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .case_analysis import case_frame, metric
from .reaction_analysis import reaction_instances


def _month_rows(series: pd.Series) -> list[dict[str, Any]]:
    counts = series.dropna().astype("string").value_counts().sort_index()
    return [{"month": str(month), "count": int(count)} for month, count in counts.items()]


def analyze_trends(frame: pd.DataFrame, *, top_n: int = 5) -> dict[str, Any]:
    cases = case_frame(frame)
    cases_by_month = _month_rows(cases["reporting_month"])
    serious_by_month = _month_rows(cases.loc[cases["normalized_serious"].eq("serious"), "reporting_month"])
    reaction_month_rows = []
    for month, rows in frame.dropna(subset=["reporting_month"]).groupby("reporting_month", sort=True):
        counts = reaction_instances(rows).value_counts().head(top_n)
        reaction_month_rows.append({"month": str(month), "top_reactions": [{"reaction": str(term), "count": int(count)} for term, count in counts.items()]})
    return {
        "cases_by_month": metric(cases_by_month, unit="cases", calculation="case_frame().groupby(reporting_month).size()", source_fields=["safetyreportid", "reporting_month", "raw_receivedate"], level="case"),
        "serious_cases_by_month": metric(serious_by_month, unit="cases", calculation="case_frame().query(normalized_serious == 'serious').groupby(reporting_month).size()", source_fields=["safetyreportid", "reporting_month", "normalized_serious", "raw_receivedate"], level="case"),
        "top_reactions_by_month": metric(reaction_month_rows, unit="reaction_instances", calculation=f"for each reporting_month, comma_split(PT).value_counts().head({top_n}); source rows retained", source_fields=["reporting_month", "patient_reaction_reactionmeddrapt"], level="reaction"),
        "interpretation_guardrail": "These are observed numerical patterns only and are not safety-signal determinations.",
    }
