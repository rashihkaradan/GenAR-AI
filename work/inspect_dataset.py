"""Deterministic inspection of the supplied Bisoprolol ICSR workbook.

This script does not modify the source workbook.  All statistics are calculated
with pandas/Python; no LLM is used for calculations.
"""
from __future__ import annotations

import json
import math
import re
from collections import OrderedDict
from pathlib import Path

import pandas as pd


SOURCE = Path(r"C:\Users\thans\Downloads\Bisoprolol_icsr_sample_1068rows.xlsx")
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

CASE_ID = "safetyreportid"
REACTION = "patient_reaction_reactionmeddrapt"
RECEIVED = "receivedate"

KNOWN_MEANINGS = {
    "safetyreportversion": "Version number of the safety report.",
    "safetyreportid": "Safety report identifier; used as the case identifier.",
    "primarysourcecountry": "Country supplied for the primary source.",
    "occurcountry": "Country where the event/case occurred.",
    "transmissiondateformat": "Format code associated with transmissiondate.",
    "transmissiondate": "Transmission date as supplied in the source extract.",
    "reporttype": "Reported case/report type.",
    "serious": "Overall serious/non-serious classification.",
    "seriousnessdeath": "Seriousness criterion: death.",
    "seriousnesslifethreatening": "Seriousness criterion: life-threatening event.",
    "seriousnesshospitalization": "Seriousness criterion: hospitalization or prolongation of hospitalization.",
    "seriousnessdisabling": "Seriousness criterion: persistent/significant disability or incapacity.",
    "seriousnesscongenitalanomali": "Seriousness criterion: congenital anomaly/birth defect (source field spelling retained).",
    "seriousnessother": "Seriousness criterion: other medically important condition.",
    "receivedateformat": "Format code associated with receivedate.",
    "receivedate": "Date the case was received; used to determine the reporting period.",
    "receiptdateformat": "Format code associated with receiptdate.",
    "receiptdate": "Receipt date as supplied in the source extract.",
    "fulfillexpeditecriteria": "Flag indicating whether the case fulfills expedited-reporting criteria; used as 15-day Alert proxy.",
    "companynumb": "Company case number as supplied in the source extract.",
    "primarysource_reportercountry": "Country of the primary reporter.",
    "primarysource_qualification": "Primary reporter qualification.",
    "patient_patientonsetage": "Patient age at onset, with unit in patient_patientonsetageunit.",
    "patient_patientonsetageunit": "Unit for patient age at onset.",
    "patient_patientsex": "Patient sex.",
    "patient_reaction_reactionmeddraversionpt": "MedDRA version(s) associated with the reported Preferred Term(s).",
    "patient_reaction_reactionmeddrapt": "Reported reaction coded as MedDRA Preferred Term(s); used for reaction analysis.",
    "patient_reaction_reactionoutcome": "Outcome(s) for reported reaction(s).",
    "patient_drug_drugcharacterization": "Drug role/characterization value(s) as supplied (for example, suspect or concomitant).",
    "patient_drug_medicinalproduct": "Medicinal product name(s) as supplied.",
    "patient_drug_drugindication": "Indication(s) for the listed drug product(s).",
    "drugs": "Drug names/active substances as supplied in the extract.",
    "report_date": "Report date field included in the source extract.",
    "patient_patientagegroup": "Coarse patient age-group field supplied in the extract.",
    "authoritynumb": "Authority number as supplied in the source extract.",
}

ANALYSIS_COLUMNS = {
    "safetyreportid", "patient_patientonsetage", "patient_patientonsetageunit",
    "patient_patientagegroup", "patient_patientsex", "occurcountry",
    "primarysource_reportercountry", "patient_reaction_reactionmeddrapt",
    "patient_reaction_reactionoutcome", "serious", "seriousnessdeath",
    "seriousnesslifethreatening", "seriousnesshospitalization", "seriousnessdisabling",
    "seriousnesscongenitalanomali", "seriousnessother", "fulfillexpeditecriteria",
    "receivedate", "patient_drug_medicinalproduct", "patient_drug_drugindication",
    "primarysource_qualification", "reporttype",
}
REACTION_LEVEL_COLUMNS = {
    "patient_reaction_reactionmeddraversionpt", "patient_reaction_reactionmeddrapt",
    "patient_reaction_reactionoutcome",
}


def jsonable(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        return value.item()
    return value


def missing_mask(series: pd.Series) -> pd.Series:
    # Treat empty/whitespace-only strings as missing in addition to pandas NA.
    return series.isna() | series.astype("string").str.strip().eq("")


def classify_level(column: str) -> str:
    if column in REACTION_LEVEL_COLUMNS:
        return "reaction-level"
    if column.startswith("patient_drug_") or column == "drugs":
        return "drug-level / delimited multi-value field"
    return "case-level"


def conservative_meaning(column: str) -> str:
    if column in KNOWN_MEANINGS:
        return KNOWN_MEANINGS[column]
    return "Not established by the supplied documentation; retained as a source field (see field name and example value)."


def parse_receivedates(raw: pd.Series) -> tuple[pd.Series, list[str]]:
    strings = raw.astype("string").str.strip()
    parsed = pd.to_datetime(strings, format="%Y%m%d", errors="coerce")
    malformed = sorted(strings[~strings.isna() & parsed.isna()].unique().tolist())
    return parsed, malformed


def split_instances(series: pd.Series) -> list[str]:
    instances: list[str] = []
    for value in series.dropna().astype(str):
        instances.extend(piece.strip() for piece in value.split(",") if piece.strip())
    return instances


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    book = pd.ExcelFile(SOURCE)
    if len(book.sheet_names) != 1:
        raise ValueError(f"Expected one source sheet, found {book.sheet_names}")
    df = pd.read_excel(SOURCE, sheet_name=book.sheet_names[0])
    df.columns = [str(c).strip() for c in df.columns]

    missing_counts = {c: int(missing_mask(df[c]).sum()) for c in df.columns}
    unique_counts = {c: int(df[c][~missing_mask(df[c])].nunique(dropna=True)) for c in df.columns}
    dtypes = {c: str(df[c].dtype) for c in df.columns}
    examples = {
        c: (None if missing_mask(df[c]).all() else jsonable(df[c][~missing_mask(df[c])].iloc[0]))
        for c in df.columns
    }

    received, malformed_received = parse_receivedates(df[RECEIVED])
    valid_received = received.dropna()
    onset_age = pd.to_numeric(df["patient_patientonsetage"], errors="coerce")
    age_units = df["patient_patientonsetageunit"].astype("string").str.strip()
    valid_age_units = {"year", "month", "week", "day"}
    invalid_age_unit_values = sorted(
        str(v) for v in age_units[~age_units.isna() & ~age_units.isin(valid_age_units)].unique()
    )
    age_outside_plausible_year_range = int(
        ((onset_age < 0) | (onset_age > 130)).sum()
    )
    case_sizes = df.groupby(CASE_ID, dropna=False).size()
    multi_case_sizes = case_sizes[case_sizes > 1]
    reaction_instances = split_instances(df[REACTION])

    # Case-level flags are reconciled by ID to identify inconsistent repeated values.
    key_case_fields = [CASE_ID, "serious", "fulfillexpeditecriteria", RECEIVED]
    case_conflicts = {}
    for column in key_case_fields[1:]:
        n_conflict = int(
            df.groupby(CASE_ID, dropna=False)[column]
            .nunique(dropna=True)
            .gt(1)
            .sum()
        )
        case_conflicts[column] = n_conflict

    serious_values = sorted(str(v) for v in df["serious"][~missing_mask(df["serious"])].unique())
    expedite_values = sorted(str(v) for v in df["fulfillexpeditecriteria"][~missing_mask(df["fulfillexpeditecriteria"])].unique())
    important_categorical_fields = [
        "serious", "fulfillexpeditecriteria", "patient_patientsex", "occurcountry",
        "primarysource_reportercountry", "primarysource_qualification", "reporttype",
        "patient_patientagegroup", "patient_reaction_reactionoutcome",
    ]
    categorical_distributions = {
        c: [
            {"value": jsonable(v), "count": int(n)}
            for v, n in df[c].value_counts(dropna=False).items()
        ]
        for c in important_categorical_fields
    }
    date_like_columns = [c for c in df.columns if "date" in c.lower()]
    date_summary = {}
    for c in date_like_columns:
        raw = df[c].astype("string").str.strip()
        date_summary[c] = {
            "non_missing_count": int((~missing_mask(df[c])).sum()),
            "example_values": [str(v) for v in raw[~raw.isna()].unique()[:5]],
        }

    warnings = []
    if SOURCE.suffix.lower() != ".csv":
        warnings.append("The supplied dataset is an .xlsx workbook rather than the CSV named in the challenge documentation; the single worksheet was analyzed without modifying it.")
    if malformed_received:
        warnings.append(f"receivedate contains {len(malformed_received)} malformed non-missing value(s): {malformed_received[:10]}")
    if invalid_age_unit_values:
        warnings.append(f"patient_patientonsetageunit contains nonstandard value(s) requiring review: {invalid_age_unit_values}")
    if age_outside_plausible_year_range:
        warnings.append("patient_patientonsetage includes numeric values outside the 0-130 range; age normalization/review is required before age bucketing.")
    if missing_counts["patient_patientagegroup"]:
        warnings.append("patient_patientagegroup is substantially missing; age analysis should derive buckets from patient_patientonsetage where valid and use the onset-age unit.")
    if any(case_conflicts.values()):
        warnings.append("At least one repeated safetyreportid has inconsistent case-level values; resolve/review before case-level aggregation.")
    if (df[REACTION].astype("string").str.contains(",", regex=False, na=False)).any():
        warnings.append("Some reaction cells contain comma-delimited multiple Preferred Terms; row count is not a count of atomic reaction instances.")
    warnings.append("No System Organ Class field is present; SOC analysis should not be inferred from Preferred Terms.")
    warnings.append("Expectedness cannot be determined because no product label/CCDS is supplied.")

    required_fields = OrderedDict([
        ("case_identification", [CASE_ID, "companynumb"]),
        ("patient_age", ["patient_patientonsetage", "patient_patientonsetageunit", "patient_patientagegroup"]),
        ("patient_sex", ["patient_patientsex"]),
        ("country", ["occurcountry", "primarysource_reportercountry", "primarysourcecountry"]),
        ("reaction_preferred_term", [REACTION, "patient_reaction_reactionmeddraversionpt"]),
        ("reaction_outcome", ["patient_reaction_reactionoutcome"]),
        ("overall_seriousness", ["serious"]),
        ("individual_seriousness_criteria", ["seriousnessdeath", "seriousnesslifethreatening", "seriousnesshospitalization", "seriousnessdisabling", "seriousnesscongenitalanomali", "seriousnessother"]),
        ("reporting_received_date", [RECEIVED, "receiptdate", "report_date"]),
        ("product", ["patient_drug_medicinalproduct", "drugs", "patient_drug_drugcharacterization"]),
        ("indication", ["patient_drug_drugindication"]),
        ("reporter_qualification", ["primarysource_qualification"]),
        ("expedited_15_day_alert_status", ["fulfillexpeditecriteria"]),
    ])

    schema = {
        "source": {"path": str(SOURCE), "format": "xlsx", "sheet": book.sheet_names[0], "source_modified": False},
        "dataset_grain": {
            "observed": "Line listing with one or more reaction/drug values per row; safetyreportid repeats across rows.",
            "case_key": CASE_ID,
            "reaction_field": REACTION,
        },
        "fields_required_for_analysis": required_fields,
        "columns": [
            {
                "name": c,
                "pandas_dtype": dtypes[c],
                "meaning": conservative_meaning(c),
                "missing_count": missing_counts[c],
                "missing_percentage": round(100 * missing_counts[c] / len(df), 2),
                "unique_non_missing_count": unique_counts[c],
                "example_value": examples[c],
                "used_in_analysis": c in ANALYSIS_COLUMNS,
                "data_level": classify_level(c),
            }
            for c in df.columns
        ],
        "date_fields": date_summary,
        "important_categorical_field_distributions": categorical_distributions,
    }

    validation = {
        "row_count": int(len(df)),
        "unique_case_count": int(df[CASE_ID].nunique(dropna=True)),
        "duplicate_row_count": int(df.duplicated().sum()),
        "reporting_period": {
            "start": valid_received.min().strftime("%Y-%m-%d"),
            "end": valid_received.max().strftime("%Y-%m-%d"),
        },
        "important_columns": {
            c: {
                "present": c in df.columns,
                "dtype": dtypes.get(c),
                "missing_count": missing_counts.get(c),
                "unique_non_missing_count": unique_counts.get(c),
            }
            for c in sorted(ANALYSIS_COLUMNS)
        },
        "missing_values": missing_counts,
        "validation_warnings": warnings,
        "additional_validation": {
            "column_count": int(len(df.columns)),
            "source_sheet": book.sheet_names[0],
            "case_ids_with_multiple_rows": int(len(multi_case_sizes)),
            "maximum_rows_for_one_case": int(case_sizes.max()),
            "row_count_vs_reaction_count": {
                "source_row_count": int(len(df)),
                "rows_with_non_missing_reaction_field": int((~missing_mask(df[REACTION])).sum()),
                "atomic_preferred_term_instances_after_comma_split": int(len(reaction_instances)),
                "definition": "Atomic Preferred Term instances are comma-split from the reaction field; this is distinct from case and source-row counts.",
            },
            "receivedate": {
                "non_missing_count": int(received.notna().sum()),
                "malformed_non_missing_values": malformed_received,
            },
            "patient_age": {
                "numeric_non_missing_count": int(onset_age.notna().sum()),
                "numeric_missing_or_non_numeric_count": int(onset_age.isna().sum()),
                "minimum_numeric_value": jsonable(onset_age.min()),
                "maximum_numeric_value": jsonable(onset_age.max()),
                "age_unit_counts_including_missing": {
                    str(k) if not pd.isna(k) else "<missing>": int(v)
                    for k, v in df["patient_patientonsetageunit"].value_counts(dropna=False).items()
                },
                "nonstandard_age_unit_values": invalid_age_unit_values,
                "values_outside_0_to_130": age_outside_plausible_year_range,
                "note": "Ages are not normalized across units; month/week/day values must be converted before a year-based age analysis.",
            },
            "case_level_field_conflicts_across_repeated_case_ids": case_conflicts,
            "categorical_values": {
                "serious": serious_values,
                "fulfillexpeditecriteria": expedite_values,
                "patient_patientsex": sorted(str(v) for v in df["patient_patientsex"][~missing_mask(df["patient_patientsex"])].unique()),
                "reporttype": sorted(str(v) for v in df["reporttype"][~missing_mask(df["reporttype"])].unique()),
                "primarysource_qualification": sorted(str(v) for v in df["primarysource_qualification"][~missing_mask(df["primarysource_qualification"])].unique()),
            },
        },
    }

    with (DATA_DIR / "schema.json").open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with (DATA_DIR / "validation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)
        f.write("\n")

    lines = [
        "# Data Dictionary",
        "",
        "Source analyzed: `Bisoprolol_icsr_sample_1068rows.xlsx`, single worksheet. The challenge documentation names a CSV; this workbook is the supplied dataset and was not modified.",
        "",
        "`case-level` means one value is expected per `safetyreportid`; repeated IDs must be reconciled before case-level analysis. `reaction-level` denotes fields that describe a reaction. Drug-level fields may contain comma-delimited values and are not assumed to align one-to-one with reactions without further validation.",
        "",
        "| Column name | Meaning | Data type | Missing | Example value | Used in analysis | Level |",
        "|---|---|---|---:|---|---|---|",
    ]
    for c in df.columns:
        example = "" if examples[c] is None else str(examples[c]).replace("|", "\\|").replace("\n", " ")[:120]
        meaning = conservative_meaning(c).replace("|", "\\|")
        lines.append(
            f"| `{c}` | {meaning} | `{dtypes[c]}` | {missing_counts[c]} ({100 * missing_counts[c] / len(df):.2f}%) | {example} | {'Yes' if c in ANALYSIS_COLUMNS else 'No'} | {classify_level(c)} |"
        )
    (ROOT / "DATA_DICTIONARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"row_count": len(df), "unique_case_count": int(df[CASE_ID].nunique()), "reaction_instances": len(reaction_instances), "output_dir": str(DATA_DIR)}, indent=2))


if __name__ == "__main__":
    main()
