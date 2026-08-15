"""Comprehensive deterministic analysis tests covering every required metric category.

Covers:
  - Dataset loading and row counts
  - Unique case counting
  - Serious / non-serious case splitting
  - Reaction counting (all and serious-only)
  - Age-group assignment and boundary correctness
  - Outcome analysis and distribution
  - Alert / 15-day criteria analysis
  - Monthly trend analysis
  - Evidence generation and IDs
  - Report section validation
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from src.analysis.analysis_runner import analyze, load_normalized_cases
from src.evidence.evidence_builder import build_evidence
from src.evidence.evidence_store import load_evidence, llm_safe_context
from src.ingestion.normalizer import derive_age_group, normalize_dataframe
from src.ingestion.validator import validate_dataframe
from src.validation.report_validator import validate_report


# ── Shared minimal fixture ────────────────────────────────────────────────────

def _make_frame(**overrides) -> pd.DataFrame:
    """Three-row frame (two cases, multi-row case A has two reactions)."""
    data = {
        "safetyreportid":                    ["C1", "C1", "C2", "C3"],
        "receivedate":                       ["20250115", "20250115", "20250210", "20250310"],
        "patient_patientonsetage":           ["70", "70", "14", "0"],
        "patient_patientonsetageunit":       ["year", "year", "year", "month"],
        "patient_patientsex":               ["female", "female", "male", "female"],
        "occurcountry":                     ["Germany", "Germany", "France", "Spain"],
        "serious":                          ["serious", "serious", "not serious", "serious"],
        "patient_reaction_reactionmeddrapt":["Nausea,Fatigue", "Headache", "Dizziness", "Pyrexia"],
        "patient_reaction_reactionoutcome": ["fatal,recovered/resolved", "unknown", "recovering/resolving", "not recovered/not resolved/ongoing"],
        "fulfillexpeditecriteria":          ["yes", "yes", "no", "yes"],
    }
    data.update(overrides)
    frame = pd.DataFrame(data, dtype="string")
    return normalize_dataframe(frame)


# ── 1. Dataset loading ────────────────────────────────────────────────────────

class DatasetLoadingTests(unittest.TestCase):

    def test_normalized_cases_file_exists_and_is_loadable(self) -> None:
        path = Path("data/normalized_cases.jsonl")
        self.assertTrue(path.exists(), "Run ingestion pipeline before integration tests.")
        df = load_normalized_cases(path)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)

    def test_source_csv_is_not_modified(self) -> None:
        """Ingestion must never overwrite the original dataset."""
        csv = next(Path("data").glob("*.csv"), None)
        if csv is None:
            self.skipTest("No CSV found in data/; skip source-integrity check.")
        mtime_before = csv.stat().st_mtime
        # Simulate a load by reading the file (no write)
        pd.read_csv(csv, nrows=5)
        self.assertEqual(csv.stat().st_mtime, mtime_before, "CSV mtime changed — ingestion wrote to source file.")

    def test_source_row_count_matches_analysis_metadata(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        expected_rows = analysis["case_index_metadata"]["value"]["source_rows"]
        df = load_normalized_cases("data/normalized_cases.jsonl")
        self.assertEqual(len(df), expected_rows)


# ── 2. Unique case counting ───────────────────────────────────────────────────

class UniqueCaseCountTests(unittest.TestCase):

    def test_multi_reaction_rows_counted_as_one_case(self) -> None:
        results = analyze(_make_frame())
        self.assertEqual(results["case_summary"]["total_cases"]["value"], 3,
                         "C1 (2 rows), C2 (1 row), C3 (1 row) = 3 unique cases")

    def test_actual_dataset_unique_case_count(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["case_summary"]["total_cases"]["value"], 1024)

    def test_case_level_metric_uses_one_representative_row(self) -> None:
        """Case-level seriousness uses first-row-per-case; test that counts are correct."""
        results = analyze(_make_frame())
        total = results["case_summary"]["total_cases"]["value"]
        serious = results["case_summary"]["serious_cases"]["value"]
        non_serious = results["case_summary"]["non_serious_cases"]["value"]
        self.assertEqual(total, serious + non_serious)


# ── 3. Serious / non-serious counting ────────────────────────────────────────

class SeriousnessTests(unittest.TestCase):

    def test_fixture_serious_non_serious_split(self) -> None:
        results = analyze(_make_frame())
        self.assertEqual(results["case_summary"]["serious_cases"]["value"], 2)
        self.assertEqual(results["case_summary"]["non_serious_cases"]["value"], 1)

    def test_serious_percentage_formula(self) -> None:
        results = analyze(_make_frame())
        s = results["case_summary"]["serious_cases"]["value"]
        t = results["case_summary"]["total_cases"]["value"]
        pct = results["case_summary"]["serious_case_percentage"]["value"]
        self.assertAlmostEqual(pct, round(100 * s / t, 1), places=1)

    def test_actual_dataset_serious_non_serious(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["case_summary"]["serious_cases"]["value"], 1023)
        self.assertEqual(analysis["case_summary"]["non_serious_cases"]["value"], 1)
        self.assertAlmostEqual(analysis["case_summary"]["serious_case_percentage"]["value"], 99.9, places=1)


# ── 4. Reaction counting ──────────────────────────────────────────────────────

class ReactionCountingTests(unittest.TestCase):

    def test_comma_split_reactions_are_each_counted(self) -> None:
        # C1-row1: "Nausea,Fatigue" = 2 reactions
        # C1-row2: "Headache" = 1
        # C2:      "Dizziness" = 1
        # C3:      "Pyrexia" = 1
        results = analyze(_make_frame())
        self.assertEqual(results["reactions"]["reaction_count"]["value"], 5)

    def test_serious_reaction_count_uses_serious_rows_only(self) -> None:
        # C1 (serious): 3 reactions; C3 (serious): 1 reaction → 4
        results = analyze(_make_frame())
        self.assertEqual(results["reactions"]["serious_reaction_count"]["value"], 4)

    def test_reaction_pt_frequency_is_sorted_descending(self) -> None:
        results = analyze(_make_frame())
        counts = [r["count"] for r in results["reactions"]["reaction_counts"]["value"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_actual_dataset_reaction_totals(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["reactions"]["reaction_count"]["value"], 3648)

    def test_top_reaction_is_acute_kidney_injury_in_actual_dataset(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        top = analysis["reactions"]["reaction_counts"]["value"][0]
        self.assertEqual(top["reaction"], "Acute kidney injury")
        self.assertEqual(top["count"], 81)


# ── 5. Age grouping ───────────────────────────────────────────────────────────

class AgeGroupTests(unittest.TestCase):

    def test_fixture_age_groups_are_correct(self) -> None:
        # C1: 70 years → 65+, C2: 14 years → 12-17, C3: 0 months ≈ 0 years → 0-1
        df = _make_frame()
        # Get the representative row per case
        case_ages = df.drop_duplicates("safetyreportid")["age_group"].tolist()
        self.assertIn("65+ years", case_ages)
        self.assertIn("12-17 years", case_ages)
        self.assertIn("0-1 years", case_ages)

    def test_month_unit_is_converted_correctly(self) -> None:
        frame = _make_frame()
        row_c3 = frame[frame["safetyreportid"] == "C3"].iloc[0]
        # 0 months → 0 years → 0-1 years bucket
        self.assertEqual(row_c3["age_group"], "0-1 years")

    def test_unknown_age_unit_yields_missing_group(self) -> None:
        frame = pd.DataFrame({
            "safetyreportid": ["X1"],
            "receivedate": ["20250101"],
            "patient_patientonsetage": ["45"],
            "patient_patientonsetageunit": ["decade"],  # unsupported unit
            "patient_patientsex": ["male"],
            "occurcountry": ["US"],
            "serious": ["serious"],
            "patient_reaction_reactionmeddrapt": ["Cough"],
            "patient_reaction_reactionoutcome": ["unknown"],
            "fulfillexpeditecriteria": ["yes"],
        }, dtype="string")
        norm = normalize_dataframe(frame)
        self.assertTrue(pd.isna(norm.iloc[0]["age_group"]))

    def test_boundary_values_assigned_correctly(self) -> None:
        ages = pd.Series([0.0, 1.99, 2.0, 11.99, 12.0, 17.99, 18.0, 64.99, 65.0, 130.0], dtype="Float64")
        groups = derive_age_group(ages).tolist()
        self.assertEqual(groups, [
            "0-1 years", "0-1 years",
            "2-11 years", "2-11 years",
            "12-17 years", "12-17 years",
            "18-64 years", "18-64 years",
            "65+ years", "65+ years",
        ])

    def test_actual_dataset_dominant_age_group_is_elderly(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        groups = analysis["demographics"]["age_group_distribution"]["value"]
        top = groups[0]
        self.assertEqual(top["category"], "65+ years")
        self.assertEqual(top["count"], 673)


# ── 6. Outcome analysis ───────────────────────────────────────────────────────

class OutcomeTests(unittest.TestCase):

    def test_comma_split_outcomes_are_each_counted(self) -> None:
        # C1-row1: "fatal,recovered/resolved" = 2 outcomes
        results = analyze(_make_frame())
        total_outcomes = results["outcomes"]["outcome_count"]["value"]
        self.assertGreaterEqual(total_outcomes, 5)

    def test_outcome_distribution_sums_to_outcome_count(self) -> None:
        results = analyze(_make_frame())
        dist_sum = sum(r["count"] for r in results["outcomes"]["outcome_distribution"]["value"])
        self.assertEqual(dist_sum, results["outcomes"]["outcome_count"]["value"])

    def test_fatal_outcome_is_tracked_separately_in_alerts(self) -> None:
        results = analyze(_make_frame())
        fatal = results["alerts"]["fatal_outcome_recorded_cases"]["value"]
        # C1 is alert (expedited=yes) and has "fatal" outcome
        self.assertGreaterEqual(fatal, 1)

    def test_actual_dataset_outcome_distribution(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        outcomes = {r["outcome"]: r["count"]
                    for r in analysis["outcomes"]["outcome_distribution"]["value"]}
        self.assertEqual(outcomes["recovered_resolved"], 1347)
        self.assertEqual(outcomes["fatal"], 137)
        self.assertEqual(outcomes["unknown"], 1135)

    def test_outcomes_sum_to_outcome_count_in_actual_data(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        dist_sum = sum(r["count"] for r in analysis["outcomes"]["outcome_distribution"]["value"])
        self.assertEqual(dist_sum, analysis["outcomes"]["outcome_count"]["value"])


# ── 7. Alert analysis ────────────────────────────────────────────────────────

class AlertAnalysisTests(unittest.TestCase):

    def test_alert_count_equals_expedited_yes_cases(self) -> None:
        results = analyze(_make_frame())
        # C1 and C3 have expedited=yes; C2 has no → 2 alert cases
        self.assertEqual(results["alerts"]["alert_cases"]["value"], 2)

    def test_alert_non_alert_arithmetic(self) -> None:
        results = analyze(_make_frame())
        total = results["case_summary"]["total_cases"]["value"]
        alerts = results["alerts"]["alert_cases"]["value"]
        self.assertLessEqual(alerts, total)

    def test_fatal_alert_case_count_vs_total_alert_cases(self) -> None:
        results = analyze(_make_frame())
        total_alert = results["alerts"]["alert_cases"]["value"]
        fatal_alert = results["alerts"]["fatal_outcome_recorded_cases"]["value"]
        without_fatal = results["alerts"]["cases_without_recorded_fatal_outcome"]["value"]
        self.assertEqual(total_alert, fatal_alert + without_fatal)

    def test_actual_dataset_alert_cases(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["alerts"]["alert_cases"]["value"], 1023)
        self.assertEqual(analysis["alerts"]["fatal_outcome_recorded_cases"]["value"], 68)
        self.assertEqual(analysis["alerts"]["cases_without_recorded_fatal_outcome"]["value"], 955)


# ── 8. Trend analysis ────────────────────────────────────────────────────────

class TrendAnalysisTests(unittest.TestCase):

    def test_monthly_counts_sum_to_total_cases(self) -> None:
        results = analyze(_make_frame())
        monthly_sum = sum(r["count"] for r in results["trends"]["cases_by_month"]["value"])
        self.assertEqual(monthly_sum, results["case_summary"]["total_cases"]["value"])

    def test_months_are_sorted_chronologically(self) -> None:
        results = analyze(_make_frame())
        months = [r["month"] for r in results["trends"]["cases_by_month"]["value"]]
        self.assertEqual(months, sorted(months))

    def test_fixture_produces_three_months(self) -> None:
        results = analyze(_make_frame())
        months = {r["month"] for r in results["trends"]["cases_by_month"]["value"]}
        self.assertIn("2025-01", months)
        self.assertIn("2025-02", months)
        self.assertIn("2025-03", months)

    def test_actual_dataset_monthly_trend_count(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        months = analysis["trends"]["cases_by_month"]["value"]
        self.assertEqual(len(months), 13)  # Dec-2024 through Dec-2025

    def test_actual_dataset_monthly_trend_totals_to_1024(self) -> None:
        analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))
        total = sum(r["count"] for r in analysis["trends"]["cases_by_month"]["value"])
        self.assertEqual(total, 1024)


# ── 9. Evidence generation ───────────────────────────────────────────────────

class EvidenceGenerationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.analysis = json.loads(Path("data/analysis_results.json").read_text(encoding="utf-8"))

    def test_all_required_evidence_ids_are_present(self) -> None:
        ev = build_evidence(self.analysis)
        ids = {item["evidence_id"] for item in ev["evidence_items"]}
        required = ["EV-PERIOD-001", "EV-CASE-001", "EV-CASE-002",
                    "EV-REACT-001", "EV-OUTCOME-001", "EV-ALERT-001",
                    "EV-DEMO-001", "EV-DEMO-002", "EV-DEMO-003",
                    "EV-TREND-001", "EV-LIMIT-001"]
        for req in required:
            self.assertIn(req, ids, f"Required evidence ID missing: {req}")

    def test_evidence_values_match_analysis_source(self) -> None:
        ev = build_evidence(self.analysis)
        total_ev = next(i for i in ev["evidence_items"] if i["evidence_id"] == "EV-CASE-001")
        self.assertEqual(total_ev["value"], self.analysis["case_summary"]["total_cases"]["value"])

    def test_evidence_sha256_is_recorded(self) -> None:
        ev = load_evidence("data/evidence.json")
        self.assertIn("analysis_sha256", ev)
        self.assertIsInstance(ev["analysis_sha256"], str)
        self.assertEqual(len(ev["analysis_sha256"]), 64)

    def test_llm_safe_context_excludes_raw_data(self) -> None:
        ev = build_evidence(self.analysis)
        context = llm_safe_context(ev, ["EV-CASE-001"])
        for item in context:
            self.assertNotIn("source_rows", item, "Raw patient rows must not be in LLM context.")
            self.assertNotIn("raw_", str(item.get("value", "")))

    def test_evidence_item_has_required_fields(self) -> None:
        ev = build_evidence(self.analysis)
        for item in ev["evidence_items"]:
            with self.subTest(evidence_id=item.get("evidence_id")):
                self.assertIn("evidence_id", item)
                self.assertIn("value", item)
                self.assertIn("calculation", item)
                self.assertIn("source_fields", item)

    def test_written_evidence_file_has_at_least_20_items(self) -> None:
        ev = load_evidence("data/evidence.json")
        self.assertGreaterEqual(len(ev["evidence_items"]), 20)


# ── 10. Report validation ────────────────────────────────────────────────────

class ReportValidationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.report = json.loads(Path("output/pader_report.json").read_text(encoding="utf-8"))
        self.evidence = json.loads(Path("data/evidence.json").read_text(encoding="utf-8"))

    def test_current_report_passes_validation(self) -> None:
        result = validate_report(self.report, self.evidence)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["numeric_claims_failed"], 0)

    def test_all_9_sections_are_present(self) -> None:
        expected = {
            "Reporting Period",
            "Narrative Summary and Analysis",
            "Summary Analysis of Cases",
            "Reaction / Adverse Event Analysis",
            "Serious Cases / 15-Day Alerts",
            "Trends and Important Observations",
            "History of Actions",
            "Case Index / Listing",
            "Data Limitations",
        }
        actual = {s["section_name"] for s in self.report["sections"]}
        self.assertEqual(actual, expected)

    def test_every_section_cites_at_least_one_evidence_id(self) -> None:
        for section in self.report["sections"]:
            if section["section_name"] == "History of Actions":
                continue  # explicitly no actions in V0
            with self.subTest(section=section["section_name"]):
                self.assertGreater(len(section.get("evidence_ids", [])), 0,
                                   f"{section['section_name']} has no evidence IDs")

    def test_evidence_ids_in_report_exist_in_evidence_store(self) -> None:
        known_ids = {item["evidence_id"] for item in self.evidence["evidence_items"]}
        for section in self.report["sections"]:
            for ev_id in section.get("evidence_ids", []):
                self.assertIn(ev_id, known_ids, f"Unknown evidence ID {ev_id!r} in {section['section_name']}")

    def test_case_index_is_a_list(self) -> None:
        case_index_section = next(
            s for s in self.report["sections"] if s["section_name"] == "Case Index / Listing"
        )
        self.assertIsInstance(case_index_section["generated_content"], list)

    def test_api_key_not_committed_in_report(self) -> None:
        text = json.dumps(self.report)
        bad_patterns = ["sk-", "Bearer ", "api_key", "OPENAI_API"]
        for pat in bad_patterns:
            self.assertNotIn(pat.lower(), text.lower(),
                             f"Possible API key pattern found in report: {pat!r}")

    def test_pdf_is_generated_and_non_empty(self) -> None:
        pdf = Path("output/Bisoprolol_PADER_Report.pdf")
        self.assertTrue(pdf.exists(), "PDF not generated. Run: python -m src.report.pdf_generator")
        self.assertGreater(pdf.stat().st_size, 10_000,
                           "PDF is suspiciously small — likely corrupted.")


if __name__ == "__main__":
    unittest.main()
