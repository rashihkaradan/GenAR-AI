"""Evidence reference and unsupported-language validation helpers."""
from __future__ import annotations

import re
from typing import Any


def validate_evidence_references(section: dict[str, Any], evidence_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return errors for missing/unknown evidence IDs and approved cited items."""
    name = section.get("section_name", "<unknown>")
    cited = section.get("evidence_ids")
    errors: list[dict[str, Any]] = []
    if not isinstance(cited, list) or not cited:
        return [{"section": name, "code": "missing_evidence_ids", "detail": "Every report section requires at least one evidence ID."}], []
    unknown = sorted(set(cited) - evidence_ids)
    if unknown:
        errors.append({"section": name, "code": "unknown_evidence_ids", "evidence_ids": unknown})
    return errors, [{"evidence_id": evidence_id} for evidence_id in cited if evidence_id in evidence_ids]


def detect_unsupported_language(section_name: str, content: str) -> list[dict[str, Any]]:
    """Flag high-risk unsupported claims while allowing explicit limitation statements."""
    lower = content.casefold()
    issues: list[dict[str, Any]] = []
    if "system organ class" in lower and not ("no system organ class" in lower or "no system organ class or causal" in lower):
        issues.append({"section": section_name, "code": "unavailable_soc_reference", "detail": "SOC is not available in the supplied data."})
    if re.search(r"\b(expected|unexpected|unlabelled|labelled)\b", lower) and not ("expectedness was not assessed" in lower or "expectedness cannot be determined" in lower):
        issues.append({"section": section_name, "code": "unsupported_expectedness_claim", "detail": "Expectedness requires a product label/CCDS."})
    history_terms = r"label(?:ing)? change|regulatory action|risk.minimi[sz]ation|safety.related study"
    if section_name == "History of Actions" and re.search(history_terms, lower) and "no history-of-actions information was supplied" not in lower:
        issues.append({"section": section_name, "code": "invented_history_of_actions", "detail": "No history-of-actions dataset was supplied."})
    if "safety signal" in lower and not ("not safety-signal" in lower or "not a safety signal" in lower or "not safety-signal determination" in lower):
        issues.append({"section": section_name, "code": "unsupported_safety_signal_claim", "detail": "Numerical trends cannot be treated as confirmed safety signals."})
    for term in ("causal relationship", "caused by", "proves"):
        if term in lower:
            issues.append({"section": section_name, "code": "unsupported_clinical_claim", "detail": f"Unsupported clinical assertion phrase: {term}."})
    return issues
