"""Exact numeric/date comparison against evidence values."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .claim_extractor import Claim, normalize_number


def _walk_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_walk_values(child) for child in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_walk_values(child) for child in value)) if value else set()
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float, Decimal)):
        return {normalize_number(str(value))}
    if isinstance(value, str):
        # Some approved category labels (for example, "0-1 years") include
        # numeric boundaries. Retain those literal values for exact matching.
        import re
        return {normalize_number(match.group(0)) for match in re.finditer(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", value)}
    return set()


def evidence_numbers(items: list[dict[str, Any]]) -> set[str]:
    """Collect exact numeric values already approved by the cited evidence items."""
    return set().union(*(_walk_values(item["value"]) for item in items)) if items else set()


def evidence_dates(items: list[dict[str, Any]]) -> set[str]:
    """Collect supplied ISO date values recursively from cited evidence items."""
    values: set[str] = set()
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
        elif isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
            values.add(value)
    for item in items: visit(item["value"])
    return values


def evidence_months(items: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
        elif isinstance(value, str) and len(value) == 7 and value[4] == "-":
            values.add(value)
    for item in items: visit(item["value"])
    return values


def validate_numeric_claims(claims: list[Claim], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return failures for literal claims absent from the section's approved evidence."""
    numbers, dates, months = evidence_numbers(items), evidence_dates(items), evidence_months(items)
    failures: list[dict[str, Any]] = []
    for claim in claims:
        if claim.kind == "date":
            if claim.value not in dates:
                failures.append({"section": claim.section, "code": "unsupported_date", "value": claim.value, "position": claim.position})
        elif claim.kind == "month":
            if claim.value not in months:
                failures.append({"section": claim.section, "code": "unsupported_month", "value": claim.value, "position": claim.position})
        else:
            normalized = normalize_number(claim.value)
            if normalized not in numbers:
                failures.append({"section": claim.section, "code": "unsupported_numeric_claim", "value": claim.value, "position": claim.position})
            elif claim.kind == "percentage":
                try:
                    Decimal(normalized)
                except InvalidOperation:
                    failures.append({"section": claim.section, "code": "invalid_percentage", "value": claim.value, "position": claim.position})
    return failures
