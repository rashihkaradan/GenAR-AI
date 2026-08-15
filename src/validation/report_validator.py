"""Fail-safe validation of the generated PADER-style report against evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.evidence.evidence_store import load_evidence, llm_safe_context

from .claim_extractor import extract_claims
from .evidence_validator import detect_unsupported_language, validate_evidence_references
from .numeric_validator import validate_numeric_claims


def _validate_case_index(section: dict[str, Any], approved_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate deterministic listing structure without treating case IDs as numeric claims."""
    content = section.get("generated_content")
    if not isinstance(content, list):
        return [{"section": section["section_name"], "code": "invalid_case_index", "detail": "Case index must be a structured list."}]
    metadata = approved_items[0]["value"] if approved_items else {}
    errors: list[dict[str, Any]] = []
    if len(content) != metadata.get("source_rows"):
        errors.append({"section": section["section_name"], "code": "case_index_row_count_mismatch", "expected": metadata.get("source_rows"), "actual": len(content)})
    identifiers = {str(row.get("case_id")) for row in content}
    if len(identifiers) != metadata.get("unique_cases"):
        errors.append({"section": section["section_name"], "code": "case_index_unique_case_count_mismatch", "expected": metadata.get("unique_cases"), "actual": len(identifiers)})
    required_fields = {"source_row_number", "case_id", "reaction_preferred_terms", "seriousness", "received_date", "country", "outcome", "expedited_alert_status"}
    if any(not required_fields.issubset(row) for row in content):
        errors.append({"section": section["section_name"], "code": "case_index_missing_required_fields"})
    return errors


def validate_report(report: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate report claims. Any error blocks automatic finalization."""
    evidence_by_id = {item["evidence_id"]: item for item in evidence["evidence_items"]}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    numeric_checked = numeric_failed = references_checked = 0
    for section in report.get("sections", []):
        reference_errors, _ = validate_evidence_references(section, set(evidence_by_id))
        errors.extend(reference_errors)
        cited_ids = section.get("evidence_ids") if isinstance(section.get("evidence_ids"), list) else []
        approved = llm_safe_context(evidence, [item for item in cited_ids if item in evidence_by_id])
        references_checked += len(cited_ids)
        name = section.get("section_name", "<unknown>")
        if name == "Case Index / Listing":
            errors.extend(_validate_case_index(section, approved))
            continue
        content = section.get("generated_content")
        if not isinstance(content, str):
            errors.append({"section": name, "code": "invalid_section_content", "detail": "Narrative report sections must contain text."})
            continue
        claims = extract_claims(name, content)
        numeric_checked += len(claims)
        numeric_issues = validate_numeric_claims(claims, approved)
        numeric_failed += len(numeric_issues)
        errors.extend(numeric_issues)
        warnings.extend(detect_unsupported_language(name, content))
    missing_sections = {"Reporting Period", "Narrative Summary and Analysis", "Summary Analysis of Cases", "Reaction / Adverse Event Analysis", "Serious Cases / 15-Day Alerts", "Trends and Important Observations", "History of Actions", "Case Index / Listing", "Data Limitations"} - {section.get("section_name") for section in report.get("sections", [])}
    if missing_sections:
        errors.append({"code": "missing_report_sections", "sections": sorted(missing_sections)})
    status = "PASS" if not errors else "FAIL"
    return {
        "status": status,
        "finalization_status": "eligible_for_human_review" if status == "PASS" else "blocked_pending_human_review",
        "numeric_claims_checked": numeric_checked,
        "numeric_claims_failed": numeric_failed,
        "evidence_references_checked": references_checked,
        "missing_evidence": [issue for issue in errors if issue["code"] in {"missing_evidence_ids", "unknown_evidence_ids"}],
        "errors": errors,
        "warnings": warnings,
    }


def safe_run(report_path: str | Path = "output/pader_report.json", evidence_path: str | Path = "data/evidence.json", output_path: str | Path = "output/validation_report.json") -> dict[str, Any]:
    """Always write a validation report, including a safe blocking report on errors."""
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        evidence = load_evidence(evidence_path)
        result = validate_report(report, evidence)
    except Exception as exc:  # Fail safely: no exception can silently mark a report final.
        result = {"status": "FAIL", "finalization_status": "blocked_pending_human_review", "numeric_claims_checked": 0, "numeric_claims_failed": 0, "evidence_references_checked": 0, "missing_evidence": [], "errors": [{"code": "validation_execution_error", "detail": str(exc)}], "warnings": []}
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a generated PADER-style report against approved evidence.")
    parser.add_argument("--report", default="output/pader_report.json")
    parser.add_argument("--evidence", default="data/evidence.json")
    parser.add_argument("--output", default="output/validation_report.json")
    args = parser.parse_args()
    result = safe_run(args.report, args.evidence, args.output)
    print(f"Report validation: {result['status']} ({result['numeric_claims_checked']} numeric/date claims checked; {result['numeric_claims_failed']} failed).")


if __name__ == "__main__":
    main()
