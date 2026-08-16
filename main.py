#!/usr/bin/env python
"""
GenAR PADER pipeline orchestrator — place this file at the project root
(alongside README.md / pytest.ini), next to the `src/` package.

Runs the full CSV -> validation -> normalization -> deterministic analysis ->
evidence -> LLM report generation -> automated validation -> (human review) ->
finalize -> PDF pipeline, matching the step order documented in README.md.

Usage
-----
    # Steps 1-5 (ingest through automated validation) in one go:
    python main.py --input data/Bisoprolol_icsr_sample_1068rows.xlsx

    # Run only specific steps:
    python main.py --input data/source.xlsx --steps ingest analyze evidence

    # After running the review UI (python -m src.review.review_ui) and
    # approving the report there:
    python main.py --steps finalize pdf

    # Demo/eval run without a human reviewer (NOT for real submissions):
    python main.py --input data/source.xlsx --steps finalize pdf --auto-approve
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from src.ingestion.validator import run_pipeline as run_ingestion
from src.analysis.analysis_runner import run as run_analysis, human_summary
from src.evidence.evidence_builder import run as run_evidence_builder
from src.reporting.report_generator import run as run_report_generation
from src.validation.report_validator import validate_report
from src.review.finalize import finalize as run_finalize
from src.review.review_store import load_review_record, submit_review, save_review_record
from src.report.pdf_generator import generate_pdf


PATHS = {
    "data_dir": Path("data"),
    "output_dir": Path("output"),
    "normalized": Path("data/normalized_cases.jsonl"),
    "dataset_validation": Path("data/validation_report.json"),
    "analysis": Path("data/analysis_results.json"),
    "evidence": Path("data/evidence.json"),
    "report": Path("output/pader_report.json"),
    "report_validation": Path("output/validation_report.json"),
    "review_record": Path("output/review_record.json"),
    "final_report": Path("output/pader_report_FINAL.json"),
    "pdf": Path("output/Bisoprolol_PADER_Report.pdf"),
}

ALL_STEPS = ["ingest", "analyze", "evidence", "generate", "validate", "finalize", "pdf"]
DEFAULT_STEPS = ["ingest", "analyze", "evidence", "generate", "validate"]


def step_ingest(args: argparse.Namespace) -> None:
    if not args.input:
        raise SystemExit("--input <csv|tsv|xlsx> is required for the 'ingest' step.")
    print(f"[1/7] Ingesting and validating: {args.input}")
    report = run_ingestion(args.input, output_dir=str(PATHS["data_dir"]))
    print(f"      rows={report['input_rows']} valid={report['valid_rows']} "
          f"invalid={report['invalid_rows']} unique_cases={report['unique_cases']}")
    if report["errors"]:
        print("      ERRORS:", report["errors"], file=sys.stderr)


def step_analyze(_: argparse.Namespace) -> None:
    print("[2/7] Running deterministic analysis")
    results = run_analysis(input_path=PATHS["normalized"], output_path=PATHS["analysis"])
    print(human_summary(results))


def step_evidence(_: argparse.Namespace) -> None:
    print("[3/7] Building evidence store")
    document = run_evidence_builder(analysis_path=PATHS["analysis"], output_path=PATHS["evidence"])
    print(f"      wrote {len(document['evidence_items'])} evidence items")


def step_generate(_: argparse.Namespace) -> None:
    print("[4/7] Generating PADER report (LLM if OPENAI_API_KEY is set, else deterministic fallback)")
    report = run_report_generation(
        output_path=PATHS["report"],
        report_validation_path=PATHS["report_validation"],
        dataset_validation_path=PATHS["dataset_validation"],
        review_record_path=PATHS["review_record"],
        evidence_path=PATHS["evidence"],
        analysis_path=PATHS["analysis"],
        normalized_path=PATHS["normalized"],
    )
    print(f"      {len(report['sections'])} sections generated using {report['model_name']}")


def step_validate(_: argparse.Namespace) -> None:
    print("[5/7] Running automated numeric validation gate")
    report = json.loads(PATHS["report"].read_text(encoding="utf-8"))
    evidence = json.loads(PATHS["evidence"].read_text(encoding="utf-8"))
    result = validate_report(report, evidence)
    PATHS["output_dir"].mkdir(parents=True, exist_ok=True)
    PATHS["report_validation"].write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"      status={result['status']} "
          f"claims_checked={result.get('numeric_claims_checked')} "
          f"claims_failed={result.get('numeric_claims_failed')}")
    if result["status"] != "PASS":
        print("      Validation FAILed — open the review UI to inspect issues before finalizing.", file=sys.stderr)


def step_finalize(args: argparse.Namespace) -> None:
    print("[6/7] Finalizing report")
    if args.auto_approve:
        print("      --auto-approve set: recording an automated approval "
              "(demo/evaluation only — not a substitute for real human review)")
        record = load_review_record(PATHS["review_record"])
        record = submit_review(
            record,
            action="approved",
            reviewer=args.auto_approve_reviewer,
            comments="Auto-approved via main.py --auto-approve (demo/eval run).",
            approved_sections=record.to_dict().get("section_names", []),
        )
        save_review_record(record, PATHS["review_record"])
    try:
        report = run_finalize(
            review_path=PATHS["review_record"],
            report_path=PATHS["report"],
            output_path=PATHS["final_report"],
        )
    except SystemExit:
        print("      Finalization blocked — see message above. Run the review UI "
              "(python -m src.review.review_ui) and approve the report, or re-run "
              "with --auto-approve for a demo run.", file=sys.stderr)
        raise
    print(f"      FINAL report written: {PATHS['final_report']} ({len(report['sections'])} sections)")


def step_pdf(_: argparse.Namespace) -> None:
    print("[7/7] Generating PDF")
    source = PATHS["final_report"] if PATHS["final_report"].exists() else PATHS["report"]
    PATHS["output_dir"].mkdir(parents=True, exist_ok=True)
    # generate_pdf(report_path, analysis_path, evidence_path, output_path) —
    # all four are paths it loads/parses itself; pass by keyword to avoid
    # positional mixups.
    generate_pdf(
        report_path=str(source),
        analysis_path=str(PATHS["analysis"]),
        evidence_path=str(PATHS["evidence"]),
        output_path=str(PATHS["pdf"]),
    )
    print(f"      PDF written: {PATHS['pdf']}")


STEP_FUNCS: dict[str, Callable[[argparse.Namespace], None]] = {
    "ingest": step_ingest,
    "analyze": step_analyze,
    "evidence": step_evidence,
    "generate": step_generate,
    "validate": step_validate,
    "finalize": step_finalize,
    "pdf": step_pdf,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the GenAR PADER pipeline end to end.")
    parser.add_argument("--input", help="Source CSV/TSV/XLSX ICSR line listing (required for 'ingest').")
    parser.add_argument(
        "--steps", nargs="+", choices=ALL_STEPS, default=None,
        help=f"Steps to run, in order. Default: {DEFAULT_STEPS} "
             "('finalize'/'pdf' need a human-reviewed report — run them explicitly once review is done).",
    )
    parser.add_argument(
        "--auto-approve", action="store_true",
        help="For the 'finalize' step only: skip the review UI and record an automatic approval. "
             "Evaluation/demo use only.",
    )
    parser.add_argument("--auto-approve-reviewer", default="main.py --auto-approve",
                         help="Reviewer name recorded when --auto-approve is used.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    steps = args.steps or DEFAULT_STEPS
    for step in steps:
        STEP_FUNCS[step](args)
    print("\nDone.")
    if "finalize" not in steps and "generate" in steps:
        print(
            "Next: run the review UI to approve the report:\n"
            "  python -m src.review.review_ui\n"
            "then:\n"
            "  python main.py --steps finalize pdf"
        )


if __name__ == "__main__":
    main()