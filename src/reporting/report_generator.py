"""Generate a complete controlled PADER-style report without exposing raw data to an LLM."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.ai.context_builder import ContextBuilder
from src.ai.generator import SectionGenerator
from src.ai.model_client import ModelClient, OpenAIResponsesClient
from src.evidence.evidence_store import load_evidence, llm_safe_context


PROMPT_VERSION = "1.0.0"
LLM_SECTIONS = {
    "Narrative Summary and Analysis": "narrative_summary",
    "Summary Analysis of Cases": "case_analysis",
    "Reaction / Adverse Event Analysis": "reaction_analysis",
    "Serious Cases / 15-Day Alerts": "alert_analysis",
    "Trends and Important Observations": "trends",
    "Data Limitations": "limitations",
}


def _item(document: dict[str, Any], evidence_id: str) -> dict[str, Any]:
    return llm_safe_context(document, [evidence_id])[0]


def _format_distribution(rows: list[dict[str, Any]], *, label: str) -> str:
    return "; ".join(f"{row.get(label, row.get('category', row.get('outcome')))}: {row['count']}" for row in rows)


class DeterministicEvidenceFallback:
    """Evidence-to-text renderer used only if no external model is configured.

    It makes no clinical assertions or calculations; it formats values already
    approved in evidence.json. This keeps the report runnable in offline CI.
    """

    model_name = "deterministic-evidence-template-fallback"

    def __init__(self, evidence_document: dict[str, Any]) -> None:
        self.evidence = evidence_document

    def render(self, section: str) -> tuple[str, list[str]]:
        get = lambda evidence_id: _item(self.evidence, evidence_id)
        if section == "Reporting Period":
            item = get("EV-PERIOD-001")
            return f"Reporting period: {item['value']['start']} to {item['value']['end']}.", [item["evidence_id"]]
        if section == "Narrative Summary and Analysis":
            period, total, serious, nonserious, top, outcomes, alerts = [get(i) for i in ["EV-PERIOD-001", "EV-CASE-001", "EV-CASE-002", "EV-CASE-003", "EV-REACT-001", "EV-OUTCOME-001", "EV-ALERT-001"]]
            top_text = _format_distribution(top["value"][:3], label="reaction")
            outcome_text = _format_distribution(outcomes["value"], label="outcome")
            return (f"During the reporting period from {period['value']['start']} to {period['value']['end']}, {total['value']} cases were received. "
                    f"Of these, {serious['value']} were classified as serious and {nonserious['value']} as non-serious. "
                    f"The most frequently reported Preferred Terms were {top_text}. Reported reaction outcomes were {outcome_text}. "
                    f"The supplied expedited criterion identified {alerts['value']} alert cases. These are descriptive observations based on the supplied data.",
                    [item["evidence_id"] for item in [period, total, serious, nonserious, top, outcomes, alerts]])
        if section == "Summary Analysis of Cases":
            total, serious, nonserious, age, sex, country, outcomes = [get(i) for i in ["EV-CASE-001", "EV-CASE-002", "EV-CASE-003", "EV-DEMO-001", "EV-DEMO-002", "EV-DEMO-003", "EV-OUTCOME-001"]]
            return (f"A total of {total['value']} unique cases were included: {serious['value']} serious and {nonserious['value']} non-serious. "
                    f"Age-group distribution was {_format_distribution(age['value'], label='category')}. "
                    f"Sex distribution was {_format_distribution(sex['value'], label='category')}. "
                    f"Occurrence-country distribution was {_format_distribution(country['value'], label='category')}. "
                    f"Reaction-outcome distribution was {_format_distribution(outcomes['value'], label='outcome')}.",
                    [item["evidence_id"] for item in [total, serious, nonserious, age, sex, country, outcomes]])
        if section == "Reaction / Adverse Event Analysis":
            reactions, serious_reactions = get("EV-REACT-001"), get("EV-REACT-002")
            return (f"The most frequently reported Preferred Terms were {_format_distribution(reactions['value'], label='reaction')}. "
                    f"Among source rows classified as serious, the most frequently reported Preferred Terms were {_format_distribution(serious_reactions['value'], label='reaction')}. "
                    "These counts describe supplied Preferred Terms only; no System Organ Class or causal interpretation is inferred.",
                    [reactions["evidence_id"], serious_reactions["evidence_id"]])
        if section == "Serious Cases / 15-Day Alerts":
            alert, seriousness, fatal, reactions, outcomes, countries = [get(i) for i in ["EV-ALERT-001", "EV-ALERT-002", "EV-ALERT-003", "EV-ALERT-007", "EV-ALERT-005", "EV-ALERT-006"]]
            return (f"The supplied expedited criterion identified {alert['value']} alert cases. Alert-case seriousness distribution was {_format_distribution(seriousness['value'], label='category')}. "
                    f"{fatal['value']} alert cases had at least one recorded fatal reaction outcome. The most frequent alert Preferred Terms were {_format_distribution(reactions['value'], label='reaction')}. "
                    f"Alert reaction outcomes were {_format_distribution(outcomes['value'], label='outcome')}. Alert occurrence countries were {_format_distribution(countries['value'], label='category')}. "
                    "Expectedness was not assessed because no product label/CCDS was supplied.",
                    [item["evidence_id"] for item in [alert, seriousness, fatal, reactions, outcomes, countries]])
        if section == "Trends and Important Observations":
            cases, serious, reactions = [get(i) for i in ["EV-TREND-001", "EV-TREND-002", "EV-TREND-003"]]
            month_cases = _format_distribution(cases["value"], label="month")
            month_serious = _format_distribution(serious["value"], label="month")
            return (f"Observed case counts by reporting month were {month_cases}. Observed serious-case counts by reporting month were {month_serious}. "
                    f"Monthly top Preferred Terms were {json.dumps(reactions['value'], ensure_ascii=False)}. These are observed numerical patterns only and are not safety-signal determinations.",
                    [item["evidence_id"] for item in [cases, serious, reactions]])
        if section == "History of Actions":
            limits = get("EV-LIMIT-001")
            return "No history-of-actions information was supplied with the dataset for this reporting interval.", [limits["evidence_id"]]
        if section == "Data Limitations":
            limits = get("EV-LIMIT-001")
            return " ".join(limits["value"]), [limits["evidence_id"]]
        raise ValueError(f"Unsupported fallback section: {section}")


def build_case_index(normalized_path: str | Path) -> list[dict[str, Any]]:
    """Create a structured reaction-row listing deterministically; this is never LLM context."""
    frame = pd.read_json(Path(normalized_path), orient="records", lines=True, dtype={"safetyreportid": "string"})
    parsed = pd.to_datetime(frame["parsed_receivedate"], errors="coerce")
    listing = pd.DataFrame({
        "source_row_number": range(1, len(frame) + 1),
        "case_id": frame["safetyreportid"].astype("string"),
        "reaction_preferred_terms": frame["patient_reaction_reactionmeddrapt"].astype("string"),
        "seriousness": frame["raw_serious"].astype("string"),
        "received_date": parsed.dt.strftime("%Y-%m-%d").astype("string"),
        "country": frame["raw_occurcountry"].astype("string"),
        "outcome": frame["raw_patient_reaction_reactionoutcome"].astype("string"),
        "expedited_alert_status": frame["raw_fulfillexpeditecriteria"].astype("string"),
    })
    return json.loads(listing.to_json(orient="records", force_ascii=False))


def _llm_client_if_configured() -> ModelClient | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    return OpenAIResponsesClient()


def generate_report(
    *,
    evidence_path: str | Path = "data/evidence.json",
    analysis_path: str | Path = "data/analysis_results.json",
    normalized_path: str | Path = "data/normalized_cases.jsonl",
    model_client: ModelClient | None = None,
) -> dict[str, Any]:
    """Generate nine report sections with evidence IDs and generation provenance."""
    evidence = load_evidence(evidence_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    client = model_client if model_client is not None else _llm_client_if_configured()
    fallback = DeterministicEvidenceFallback(evidence)
    model_name = getattr(client, "model_name", None) if client else fallback.model_name
    context = ContextBuilder.from_paths(evidence_path, analysis_path)
    llm_generator = SectionGenerator(context, client) if client else None
    sections: list[dict[str, Any]] = []
    for display_name, ai_section in LLM_SECTIONS.items():
        if llm_generator:
            generated = llm_generator.generate(ai_section)
            content, evidence_ids = generated.content, generated.evidence_ids
        else:
            content, evidence_ids = fallback.render(display_name)
        sections.append({"section_name": display_name, "generated_content": content, "evidence_ids": evidence_ids, "generation_timestamp": timestamp, "model_name": model_name, "prompt_version": PROMPT_VERSION})
    for display_name in ["Reporting Period", "History of Actions"]:
        content, evidence_ids = fallback.render(display_name)
        sections.append({"section_name": display_name, "generated_content": content, "evidence_ids": evidence_ids, "generation_timestamp": timestamp, "model_name": "deterministic-evidence-template", "prompt_version": PROMPT_VERSION})
    index_meta = _item(evidence, "EV-INDEX-001")
    sections.append({
        "section_name": "Case Index / Listing",
        "generated_content": build_case_index(normalized_path),
        "evidence_ids": [index_meta["evidence_id"]],
        "generation_timestamp": timestamp,
        "model_name": "deterministic-case-index-builder",
        "prompt_version": PROMPT_VERSION,
    })
    desired_order = ["Reporting Period", "Narrative Summary and Analysis", "Summary Analysis of Cases", "Reaction / Adverse Event Analysis", "Serious Cases / 15-Day Alerts", "Trends and Important Observations", "History of Actions", "Case Index / Listing", "Data Limitations"]
    sections.sort(key=lambda section: desired_order.index(section["section_name"]))
    return {"report_type": "PADER-style report", "generation_timestamp": timestamp, "model_name": model_name, "prompt_version": PROMPT_VERSION, "evidence_source": Path(evidence_path).name, "sections": sections}


def run(output_path: str | Path = "output/pader_report.json", **kwargs: Any) -> dict[str, Any]:
    report = generate_report(**kwargs)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an evidence-grounded PADER-style report.")
    parser.add_argument("--output", default="output/pader_report.json")
    parser.add_argument("--evidence", default="data/evidence.json")
    parser.add_argument("--analysis", default="data/analysis_results.json")
    parser.add_argument("--normalized", default="data/normalized_cases.jsonl")
    args = parser.parse_args()
    report = run(args.output, evidence_path=args.evidence, analysis_path=args.analysis, normalized_path=args.normalized)
    print(f"Generated {len(report['sections'])} PADER-style sections at {args.output} using {report['model_name']}.")


if __name__ == "__main__":
    main()
