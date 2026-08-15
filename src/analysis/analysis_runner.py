"""Run the complete deterministic analysis and write evidence-traceable JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .alert_analysis import analyze_alerts
from .case_analysis import analyze_cases, case_frame, metric
from .demographic_analysis import analyze_demographics
from .outcome_analysis import analyze_outcomes
from .reaction_analysis import analyze_reactions
from .trend_analysis import analyze_trends


def load_normalized_cases(path: str | Path) -> pd.DataFrame:
    """Load JSON Lines normalization output, keeping source records intact."""
    frame = pd.read_json(Path(path), orient="records", lines=True, dtype={"safetyreportid": "string"})
    frame["reporting_month"] = frame["reporting_month"].astype("string")
    return frame


def analyze(frame: pd.DataFrame) -> dict[str, Any]:
    """Produce the requested deterministic analysis object."""
    dates = pd.to_datetime(frame["parsed_receivedate"], errors="coerce").dropna()
    reporting_period = {
        "start_date": metric(dates.min().strftime("%Y-%m-%d") if not dates.empty else None, unit="date", calculation="min(parsed_receivedate)", source_fields=["receivedate", "parsed_receivedate"], level="case"),
        "end_date": metric(dates.max().strftime("%Y-%m-%d") if not dates.empty else None, unit="date", calculation="max(parsed_receivedate)", source_fields=["receivedate", "parsed_receivedate"], level="case"),
    }
    reactions = analyze_reactions(frame)
    return {
        "reporting_period": reporting_period,
        "case_summary": analyze_cases(frame),
        "demographics": analyze_demographics(frame),
        "reactions": reactions,
        "serious_reactions": reactions["serious_reaction_counts"],
        "outcomes": analyze_outcomes(frame),
        "alerts": analyze_alerts(frame),
        "trends": analyze_trends(frame),
        "limitations": [
            "Case-level metrics use one reproducible representative row per safetyreportid; validation warns when case-level values conflict across rows.",
            "Reaction and outcome cells can be comma-delimited. They are split only to count supplied instances; no reaction rows or instances are deduplicated.",
            "No System Organ Class analysis is performed because no SOC field is supplied.",
            "Expectedness is not assessed because no product label or CCDS is supplied.",
            "Observed trends are numerical descriptions, not safety-signal conclusions.",
        ],
    }


def human_summary(results: dict[str, Any]) -> str:
    cases = results["case_summary"]
    period = results["reporting_period"]
    reactions = results["reactions"]["most_frequently_reported_reactions"]["value"][:3]
    top = "; ".join(f"{entry['reaction']}: {entry['count']}" for entry in reactions)
    return "\n".join([
        "Deterministic PADER analysis summary",
        f"Reporting period: {period['start_date']['value']} to {period['end_date']['value']}",
        f"Cases: {cases['total_cases']['value']} total; {cases['serious_cases']['value']} serious; {cases['non_serious_cases']['value']} non-serious ({cases['serious_case_percentage']['value']}% serious).",
        f"Reaction instances: {results['reactions']['reaction_count']['value']}.",
        f"Top reported reactions: {top}",
        f"Alert cases: {results['alerts']['alert_cases']['value']}.",
        "All trend outputs are observed numerical patterns, not safety-signal determinations.",
    ])


def run(input_path: str | Path = "data/normalized_cases.jsonl", output_path: str | Path = "data/analysis_results.json") -> dict[str, Any]:
    results = analyze(load_normalized_cases(input_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic GenAR PADER analysis.")
    parser.add_argument("--input", default="data/normalized_cases.jsonl")
    parser.add_argument("--output", default="data/analysis_results.json")
    args = parser.parse_args()
    print(human_summary(run(args.input, args.output)))


if __name__ == "__main__":
    main()
