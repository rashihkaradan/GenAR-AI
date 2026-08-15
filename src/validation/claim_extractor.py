"""Conservative extraction of numeric and date claims from report prose."""
from __future__ import annotations

import re
from dataclasses import dataclass


DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
MONTH_PATTERN = re.compile(r"\b\d{4}-\d{2}\b")
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|\b\d+(?:\.\d+)?%?")


@dataclass(frozen=True)
class Claim:
    section: str
    value: str
    kind: str  # number, percentage, date
    position: int


def extract_claims(section: str, content: str) -> list[Claim]:
    """Extract literal numeric/percentage/date values from narrative prose.

    Dates are extracted first and removed before numeric matching so their year,
    month, and day components cannot create false numeric claims.
    """
    claims = [Claim(section, match.group(0), "date", match.start()) for match in DATE_PATTERN.finditer(content)]
    masked = DATE_PATTERN.sub(lambda match: " " * len(match.group(0)), content)
    claims.extend(Claim(section, match.group(0), "month", match.start()) for match in MONTH_PATTERN.finditer(masked))
    masked = MONTH_PATTERN.sub(lambda match: " " * len(match.group(0)), masked)
    for match in NUMBER_PATTERN.finditer(masked):
        raw = match.group(0)
        claims.append(Claim(section, raw.rstrip("%"), "percentage" if raw.endswith("%") else "number", match.start()))
    return sorted(claims, key=lambda claim: claim.position)


def normalize_number(value: str) -> str:
    """Canonicalize formatted number literals for exact deterministic comparison."""
    plain = value.replace(",", "")
    if "." in plain:
        plain = plain.rstrip("0").rstrip(".")
    return plain
