"""Build deterministic, claim-ready evidence from analysis_results.json only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .claim_schema import EvidenceItem
from .evidence_store import save_evidence


GLOBAL_LIMITATIONS = [
    "No System Organ Class field is available; SOC analysis is not performed.",
    "No product label/CCDS is supplied; expectedness cannot be determined.",
    "No history-of-actions data is supplied.",
    "Source-row count differs from unique case count; case metrics use unique safetyreportid values and reaction metrics retain supplied reaction instances.",
    "Individual seriousness flags are independent fields and are not mutually exclusive.",
]


def _metric_item(
    evidence_id: str,
    metric_name: str,
    analysis_name: str,
    source: dict[str, Any],
    *,
    filters: list[str] | None = None,
    limitations: list[str] | None = None,
    level: str | None = None,
) -> EvidenceItem:
    """Convert a precomputed metric object to evidence without recalculation."""
    return EvidenceItem(
        evidence_id=evidence_id,
        metric=metric_name,
        value=source["value"],
        unit=source["unit"],
        analysis_name=analysis_name,
        source_fields=source["source_fields"],
        calculation=source["calculation"],
        filters=filters or [],
        case_level_or_reaction_level=level or source["analysis_level"],
        limitations=limitations or [],
    )


def build_evidence(analysis: dict[str, Any]) -> dict[str, Any]:
    """Create the approved evidence boundary from deterministic analysis results.

    This function accepts an analysis object only. It does not load a CSV, workbook,
    normalized case line listing, or external data source.
    """
    items: list[EvidenceItem] = []
    period = analysis["reporting_period"]
    items.append(EvidenceItem(
        evidence_id="EV-PERIOD-001",
        metric="reporting_period",
        value={"start": period["start_date"]["value"], "end": period["end_date"]["value"]},
        unit="date_range",
        analysis_name="reporting_period",
        source_fields=sorted(set(period["start_date"]["source_fields"] + period["end_date"]["source_fields"])),
        calculation="min(parsed_receivedate) and max(parsed_receivedate)",
        filters=[],
        case_level_or_reaction_level="case",
        limitations=[],
    ))
    case = analysis["case_summary"]
    items.extend([
        _metric_item("EV-CASE-001", "total_cases", "unique_case_count", case["total_cases"]),
        _metric_item("EV-CASE-002", "serious_cases", "serious_case_count", case["serious_cases"], filters=["normalized_serious == 'serious'"]),
        _metric_item("EV-CASE-003", "non_serious_cases", "non_serious_case_count", case["non_serious_cases"], filters=["normalized_serious == 'not_serious'"]),
        _metric_item("EV-CASE-004", "serious_case_percentage", "serious_case_percentage", case["serious_case_percentage"], filters=["normalized_serious == 'serious'"], limitations=["Percentage uses total unique cases as denominator."]),
    ])
    demographics = analysis["demographics"]
    items.extend([
        _metric_item("EV-DEMO-001", "age_group_distribution", "demographic_age_group_distribution", demographics["age_group_distribution"], limitations=["Unknown, missing, nonstandard, or impossible ages remain missing; no age is assumed."]),
        _metric_item("EV-DEMO-002", "sex_distribution", "demographic_sex_distribution", demographics["sex_distribution"], limitations=["Distribution uses supplied sex values normalized only for formatting."]),
        _metric_item("EV-DEMO-003", "country_distribution", "demographic_country_distribution", demographics["country_distribution"], limitations=["Country is occurrence country; repeated cases with conflicting country values use the documented representative-row policy."]),
    ])
    reactions = analysis["reactions"]
    items.extend([
        _metric_item("EV-REACT-001", "top_reactions", "reaction_frequency", reactions["most_frequently_reported_reactions"], limitations=["Counts are supplied comma-delimited Preferred Term instances; no SOC is inferred."]),
        _metric_item("EV-REACT-002", "top_serious_reactions", "serious_reaction_frequency", reactions["most_frequently_reported_serious_reactions"], filters=["normalized_serious == 'serious'"], limitations=["Counts are supplied comma-delimited Preferred Term instances; no SOC is inferred."]),
    ])
    items.append(_metric_item("EV-OUTCOME-001", "outcome_distribution", "reaction_outcome_distribution", analysis["outcomes"]["outcome_distribution"], limitations=["Outcomes are reaction-level supplied values; no clinical outcome is imputed."]))
    alerts = analysis["alerts"]
    items.extend([
        _metric_item("EV-ALERT-001", "alert_cases", "expedited_alert_case_count", alerts["alert_cases"], filters=["normalized_expedited == 'yes'"], limitations=["Alert status is based on the supplied expedited criterion; expectedness is not inferred."]),
        _metric_item("EV-ALERT-002", "alert_serious_non_serious_distribution", "expedited_alert_seriousness_distribution", alerts["serious_non_serious_distribution"], filters=["normalized_expedited == 'yes'"], limitations=["Seriousness is the supplied overall classification."]),
        _metric_item("EV-ALERT-003", "alert_fatal_outcome_recorded_cases", "expedited_alert_fatal_outcome_cases", alerts["fatal_outcome_recorded_cases"], filters=["normalized_expedited == 'yes'", "any normalized_outcome == 'fatal'"], limitations=["A recorded fatal outcome does not establish causal attribution."]),
        _metric_item("EV-ALERT-004", "alert_reaction_distribution", "expedited_alert_reaction_distribution", alerts["reaction_distribution"], filters=["normalized_expedited == 'yes'"], limitations=["Reaction instances are not deduplicated."]),
        _metric_item("EV-ALERT-005", "alert_outcome_distribution", "expedited_alert_outcome_distribution", alerts["outcome_distribution"], filters=["normalized_expedited == 'yes'"]),
        _metric_item("EV-ALERT-006", "alert_country_distribution", "expedited_alert_country_distribution", alerts["country_distribution"], filters=["normalized_expedited == 'yes'"]),
        _metric_item("EV-ALERT-007", "top_alert_reactions", "expedited_alert_top_reactions", alerts["top_reactions"], filters=["normalized_expedited == 'yes'"], limitations=["Reaction instances are not deduplicated; this is a top-frequency subset of the full deterministic alert reaction distribution."]),
    ])
    trends = analysis["trends"]
    trend_limit = ["Observed numerical patterns only; not a safety-signal determination."]
    items.extend([
        _metric_item("EV-TREND-001", "cases_by_month", "monthly_case_counts", trends["cases_by_month"], limitations=trend_limit),
        _metric_item("EV-TREND-002", "serious_cases_by_month", "monthly_serious_case_counts", trends["serious_cases_by_month"], filters=["normalized_serious == 'serious'"], limitations=trend_limit),
        _metric_item("EV-TREND-003", "top_reactions_by_month", "monthly_top_reactions", trends["top_reactions_by_month"], limitations=trend_limit),
    ])
    items.append(EvidenceItem(
        evidence_id="EV-LIMIT-001",
        metric="limitations",
        value=GLOBAL_LIMITATIONS,
        unit="limitations",
        analysis_name="analysis_limitations",
        source_fields=[],
        calculation="Deterministic scope and data-availability constraints carried from the validated analysis configuration.",
        filters=[],
        case_level_or_reaction_level="report",
        limitations=GLOBAL_LIMITATIONS,
    ))
    return {
        "evidence_version": "1.0.0",
        "evidence_policy": "LLM consumers may receive only evidence_items selected from this document. Raw CSV/workbook and normalized line listings are outside this interface.",
        "analysis_sha256": hashlib.sha256(json.dumps(analysis, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "evidence_items": [item.to_dict() for item in items],
    }


def run(analysis_path: str | Path = "data/analysis_results.json", output_path: str | Path = "data/evidence.json") -> dict[str, Any]:
    """Load approved analysis results and write validated evidence."""
    analysis = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    document = build_evidence(analysis)
    save_evidence(document, output_path)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic LLM-safe evidence from analysis results.")
    parser.add_argument("--analysis", default="data/analysis_results.json")
    parser.add_argument("--output", default="data/evidence.json")
    args = parser.parse_args()
    evidence = run(args.analysis, args.output)
    print(f"Created {len(evidence['evidence_items'])} deterministic evidence items at {args.output}.")


if __name__ == "__main__":
    main()
