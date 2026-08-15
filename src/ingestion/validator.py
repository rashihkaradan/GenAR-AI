"""Deterministic validation and reproducible validation-report generation."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .loader import load_dataset
from .normalizer import AGE_UNIT_TO_YEARS, EXPEDITED_MAP, OUTCOME_MAP, SERIOUS_MAP, SEX_MAP, clean_text


REQUIRED_COLUMNS = (
    "safetyreportid", "receivedate", "patient_patientonsetage", "patient_patientonsetageunit",
    "patient_patientsex", "occurcountry", "serious", "patient_reaction_reactionmeddrapt",
    "patient_reaction_reactionoutcome", "fulfillexpeditecriteria",
)
CASE_LEVEL_COLUMNS = ("receivedate", "serious", "fulfillexpeditecriteria", "occurcountry", "patient_patientsex")


def missing(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().eq("")


@dataclass
class ValidationResult:
    row_valid: pd.Series
    report: dict[str, Any]


def _unexpected_values(series: pd.Series, allowed: set[str]) -> list[str]:
    cleaned = clean_text(series)
    return sorted(str(value) for value in cleaned[~cleaned.isna() & ~cleaned.isin(allowed)].unique())


def validate_dataframe(frame: pd.DataFrame) -> ValidationResult:
    """Validate supplied records without dropping rows or changing their values."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    absent = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if absent:
        errors.append({"code": "missing_required_columns", "columns": absent})
        return ValidationResult(pd.Series(False, index=frame.index), {
            "input_rows": int(len(frame)), "valid_rows": 0, "invalid_rows": int(len(frame)),
            "unique_cases": 0, "missing_fields": {}, "warnings": warnings, "errors": errors,
            "reporting_period": {"start": None, "end": None},
        })

    id_missing = missing(frame["safetyreportid"])
    parsed_date = pd.to_datetime(frame["receivedate"], format="%Y%m%d", errors="coerce")
    invalid_date = ~missing(frame["receivedate"]) & parsed_date.isna()
    reaction_missing = missing(frame["patient_reaction_reactionmeddrapt"])
    row_valid = ~(id_missing | invalid_date | reaction_missing)

    for code, mask, detail in (
        ("missing_case_id", id_missing, "safetyreportid is required for case-level aggregation."),
        ("invalid_receivedate", invalid_date, "receivedate must use YYYYMMDD."),
        ("missing_reaction_term", reaction_missing, "Reaction terms must remain present at reaction level."),
    ):
        count = int(mask.sum())
        if count:
            warnings.append({"code": code, "count": count, "detail": detail})

    age_numeric = pd.to_numeric(frame["patient_patientonsetage"], errors="coerce")
    age_present = ~missing(frame["patient_patientonsetage"])
    nonnumeric_age = age_present & age_numeric.isna()
    age_unit = clean_text(frame["patient_patientonsetageunit"])
    unknown_age_unit = age_present & (~age_unit.isin(set(AGE_UNIT_TO_YEARS)) | age_unit.isna())
    age_years = age_numeric * age_unit.map(AGE_UNIT_TO_YEARS)
    impossible_age = age_years.notna() & ((age_years < 0) | (age_years > 130))
    for code, mask in (("nonnumeric_age", nonnumeric_age), ("unexpected_age_unit", unknown_age_unit), ("impossible_age", impossible_age)):
        if int(mask.sum()):
            warnings.append({"code": code, "count": int(mask.sum())})

    categorical_rules = {
        "patient_patientsex": set(SEX_MAP),
        "serious": set(SERIOUS_MAP),
        "fulfillexpeditecriteria": set(EXPEDITED_MAP),
    }
    for column, accepted in categorical_rules.items():
        values = _unexpected_values(frame[column], accepted)
        if values:
            warnings.append({"code": "unexpected_categorical_values", "column": column, "values": values, "count": len(values)})

    # Outcomes can be comma-delimited. Validate the individual supplied outcomes.
    outcome_terms = frame["patient_reaction_reactionoutcome"].dropna().astype("string").str.split(",").explode()
    outcome_values = _unexpected_values(outcome_terms, set(OUTCOME_MAP))
    if outcome_values:
        warnings.append({"code": "unexpected_categorical_values", "column": "patient_reaction_reactionoutcome", "values": outcome_values, "count": len(outcome_values)})

    for column in CASE_LEVEL_COLUMNS:
        conflicts = frame.loc[~id_missing].groupby("safetyreportid")[column].nunique(dropna=True).gt(1)
        count = int(conflicts.sum())
        if count:
            warnings.append({"code": "inconsistent_case_level_values", "column": column, "case_count": count})

    missing_fields = {column: int(missing(frame[column]).sum()) for column in REQUIRED_COLUMNS}
    period = parsed_date.dropna()
    report = {
        "input_rows": int(len(frame)),
        "valid_rows": int(row_valid.sum()),
        "invalid_rows": int((~row_valid).sum()),
        "unique_cases": int(frame.loc[~id_missing, "safetyreportid"].nunique()),
        "missing_fields": missing_fields,
        "warnings": warnings,
        "errors": errors,
        "reporting_period": {
            "start": period.min().strftime("%Y-%m-%d") if not period.empty else None,
            "end": period.max().strftime("%Y-%m-%d") if not period.empty else None,
        },
        "methodology": {
            "case_key": "safetyreportid",
            "reaction_handling": "No reaction rows are deduplicated, split, or discarded. Case counts use unique non-missing safetyreportid values.",
            "missing_data_policy": "Missing clinical values remain missing; no values are imputed.",
            "scope_exclusions": ["No System Organ Class is inferred.", "No expectedness is inferred without label/CCDS data."],
        },
    }
    return ValidationResult(row_valid=row_valid, report=report)


def run_pipeline(input_path: str | Path, output_dir: str | Path = "data") -> dict[str, Any]:
    """Load, validate, normalize, and write deterministic JSON Lines and report outputs."""
    from .normalizer import normalize_dataframe

    source = Path(input_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame = load_dataset(source)
    result = validate_dataframe(frame)
    normalized = normalize_dataframe(frame)
    # JSON Lines is selected because no parquet engine is bundled; it retains all rows and nullable fields.
    normalized.to_json(output / "normalized_cases.jsonl", orient="records", lines=True, date_format="iso", force_ascii=False)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {
        **result.report,
        "source_file": source.name,
        "source_sha256": source_sha256,
        "normalized_output": "normalized_cases.jsonl",
        "normalization_version": "1.0.0",
    }
    (output / "validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and normalize a GenAR ICSR line listing.")
    parser.add_argument("input_path", help="CSV, TSV, XLSX, or XLS source file")
    parser.add_argument("--output-dir", default="data", help="Directory for validation outputs")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.input_path, args.output_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
