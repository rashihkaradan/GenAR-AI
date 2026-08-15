"""Lossless, deterministic normalization of ICSR fields used in analysis.

No clinical fact is inferred. Normalized values are only standardized renderings of
the supplied values; raw columns remain available for traceability.
"""
from __future__ import annotations

from typing import Final

import pandas as pd


AGE_GROUP_RULES: Final[tuple[str, ...]] = (
    "0-1 years: normalized age >= 0 and < 2 years",
    "2-11 years: normalized age >= 2 and < 12 years",
    "12-17 years: normalized age >= 12 and < 18 years",
    "18-64 years: normalized age >= 18 and < 65 years",
    "65+ years: normalized age >= 65 and <= 130 years",
    "Missing when age/unit is missing, nonnumeric, nonstandard, or impossible.",
)

SEX_MAP: Final[dict[str, str]] = {
    "male": "male", "m": "male", "female": "female", "f": "female",
    "unknown": "unknown", "not specified": "unknown", "unspecified": "unknown",
}
SERIOUS_MAP: Final[dict[str, str]] = {
    "serious": "serious", "not serious": "not_serious", "non-serious": "not_serious", "non serious": "not_serious",
}
EXPEDITED_MAP: Final[dict[str, str]] = {
    "yes": "yes", "y": "yes", "true": "yes", "1": "yes",
    "no": "no", "n": "no", "false": "no", "0": "no",
}
OUTCOME_MAP: Final[dict[str, str]] = {
    "recovered/resolved": "recovered_resolved",
    "recovering/resolving": "recovering_resolving",
    "not recovered/not resolved": "not_recovered_not_resolved",
    "not recovered/not resolved/ongoing": "not_recovered_not_resolved_ongoing",
    "recovered/resolved with sequelae": "recovered_resolved_with_sequelae",
    "fatal": "fatal",
    "unknown": "unknown",
}
AGE_UNIT_TO_YEARS: Final[dict[str, float]] = {
    "year": 1.0, "month": 1 / 12, "week": 1 / 52.1775, "day": 1 / 365.25,
}


def clean_text(series: pd.Series) -> pd.Series:
    """Trim and casefold supplied text; retain missing values as ``pd.NA``."""
    value = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.casefold()
    return value.mask(value.eq(""))


def normalize_category(series: pd.Series, mapping: dict[str, str]) -> pd.Series:
    """Map known source values; retain unexpected normalized source text unchanged."""
    cleaned = clean_text(series)
    return cleaned.map(mapping).fillna(cleaned).astype("string")


def normalize_outcome(series: pd.Series) -> pd.Series:
    """Normalize each comma-delimited reaction outcome while retaining its cardinality."""
    def one(value: object) -> object:
        if pd.isna(value) or not str(value).strip():
            return pd.NA
        terms = [term.strip().casefold() for term in str(value).split(",")]
        return ",".join(OUTCOME_MAP.get(term, term) for term in terms)

    return series.map(one).astype("string")


def normalized_age_years(age: pd.Series, unit: pd.Series) -> pd.Series:
    """Convert only documented age units; unknown units deliberately remain missing."""
    numeric_age = pd.to_numeric(age, errors="coerce")
    factor = clean_text(unit).map(AGE_UNIT_TO_YEARS)
    years = numeric_age * factor
    return years.mask((years < 0) | (years > 130)).astype("Float64")


def derive_age_group(age_years: pd.Series) -> pd.Series:
    groups = pd.Series(pd.NA, index=age_years.index, dtype="string")
    groups.loc[age_years.ge(0) & age_years.lt(2)] = "0-1 years"
    groups.loc[age_years.ge(2) & age_years.lt(12)] = "2-11 years"
    groups.loc[age_years.ge(12) & age_years.lt(18)] = "12-17 years"
    groups.loc[age_years.ge(18) & age_years.lt(65)] = "18-64 years"
    groups.loc[age_years.ge(65) & age_years.le(130)] = "65+ years"
    return groups


def normalize_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with traceability and derived fields, preserving every source row."""
    normalized = frame.copy(deep=True)
    raw_columns = {
        "patient_patientonsetage": "raw_patient_patientonsetage",
        "patient_patientonsetageunit": "raw_patient_patientonsetageunit",
        "patient_patientsex": "raw_patient_patientsex",
        "occurcountry": "raw_occurcountry",
        "serious": "raw_serious",
        "patient_reaction_reactionoutcome": "raw_patient_reaction_reactionoutcome",
        "fulfillexpeditecriteria": "raw_fulfillexpeditecriteria",
        "receivedate": "raw_receivedate",
    }
    for source, raw_name in raw_columns.items():
        if source in normalized:
            normalized[raw_name] = normalized[source]

    if "receivedate" in normalized:
        normalized["parsed_receivedate"] = pd.to_datetime(
            normalized["receivedate"], format="%Y%m%d", errors="coerce"
        )
        normalized["reporting_month"] = normalized["parsed_receivedate"].dt.strftime("%Y-%m").astype("string")
    if {"patient_patientonsetage", "patient_patientonsetageunit"}.issubset(normalized.columns):
        normalized["normalized_age_years"] = normalized_age_years(
            normalized["patient_patientonsetage"], normalized["patient_patientonsetageunit"]
        )
        normalized["age_group"] = derive_age_group(normalized["normalized_age_years"])
    if "patient_patientsex" in normalized:
        normalized["normalized_sex"] = normalize_category(normalized["patient_patientsex"], SEX_MAP)
    if "occurcountry" in normalized:
        # Country is only whitespace/case normalized; no ISO country code is inferred.
        normalized["normalized_country"] = clean_text(normalized["occurcountry"])
    if "serious" in normalized:
        normalized["normalized_serious"] = normalize_category(normalized["serious"], SERIOUS_MAP)
    if "patient_reaction_reactionoutcome" in normalized:
        normalized["normalized_outcome"] = normalize_outcome(normalized["patient_reaction_reactionoutcome"])
    if "fulfillexpeditecriteria" in normalized:
        normalized["normalized_expedited"] = normalize_category(normalized["fulfillexpeditecriteria"], EXPEDITED_MAP)
    # Reaction PT is deliberately not transformed or split: each original row is retained.
    return normalized
