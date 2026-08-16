"""CLI finalization tool for GenAR PADER reports.

Usage:
    python -m src.review.finalize [--review output/review_record.json]
                                   [--report output/pader_report.json]
                                   [--out    output/pader_report_FINAL.json]

A report is only finalized when:
  * validation_status == "PASS"   (automated pipeline gate)
  * review_status     == "approved" (human approval gate)

Any other combination exits with code 1 and an explanatory message.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .review_store import load_review_record


def _load_report(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        print(f"ERROR: Report not found at {report_path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(report_path.read_text(encoding="utf-8"))


def finalize(
    review_path: str | Path = "output/review_record.json",
    report_path: str | Path = "output/pader_report.json",
    output_path: str | Path = "output/pader_report_FINAL.json",
) -> dict[str, Any]:
    """Produce a final report or exit(1) with a clear message."""
    review_path = Path(review_path)
    report_path = Path(report_path)
    output_path = Path(output_path)

    if not review_path.exists():
        print(
            f"ERROR: No review record found at {review_path}.\n"
            "Run the review UI and submit an approval first.",
            file=sys.stderr,
        )
        sys.exit(1)

    record = load_review_record(review_path)

    # Gate 1 — automated validation
    if record.validation_status != "PASS":
        print(
            f"BLOCKED: Report cannot be finalized.\n"
            f"  validation_status = {record.validation_status!r} (must be 'PASS')\n"
            "  Resolve all validation errors, regenerate the report, and re-submit for review.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Gate 2 — human approval
    if record.review_status != "approved":
        print(
            f"BLOCKED: Report cannot be finalized.\n"
            f"  review_status = {record.review_status!r} (must be 'approved')\n"
            "  A qualified human reviewer must approve the report before finalization.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Both gates passed — write the FINAL report
    report = _load_report(report_path)
    finalization_timestamp = datetime.now(timezone.utc).isoformat()
    report["finalization_status"] = "final"
    report["finalization_timestamp"] = finalization_timestamp
    report["human_review"] = {
        "review_status": record.review_status,
        "reviewer": record.to_dict().get("reviewer"),
        "timestamp": record.to_dict().get("timestamp"),
        "comments": record.to_dict().get("comments", ""),
        "approved_sections": record.to_dict().get("approved_sections", []),
        "flagged_sections": record.to_dict().get("flagged_sections", []),
        "report_id": record.report_id,
        "validation_status": record.validation_status,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize a human-approved PADER report."
    )
    parser.add_argument("--review", default="output/review_record.json")
    parser.add_argument("--report", default="output/pader_report.json")
    parser.add_argument("--out", default="output/pader_report_FINAL.json")
    args = parser.parse_args()

    report = finalize(
        review_path=args.review,
        report_path=args.report,
        output_path=args.out,
    )
    print(
        f"OK  FINAL report written to {args.out}\n"
        f"  Sections:    {len(report['sections'])}\n"
        f"  Reviewer:    {report['human_review']['reviewer']}\n"
        f"  Approved at: {report['human_review']['timestamp']}\n"
        f"  Finalized:   {report['finalization_timestamp']}"
    )


if __name__ == "__main__":
    main()
