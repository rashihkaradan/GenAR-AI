"""Core review store: create, load, update, and persist PADER review records.

A report can only be marked FINAL after:
  1. Its validation_status is PASS
  2. A human reviewer explicitly sets review_status to "approved"

An unvalidated (FAIL) report can never be approved — ReviewBlockedError is raised.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REVIEW_VERSION = "1.0.0"

VALID_ACTIONS = frozenset({"approved", "flagged", "rejected"})


class ReviewBlockedError(Exception):
    """Raised when a reviewer attempts to approve a report that fails validation."""


class ReviewRecord:
    """Lightweight wrapper around the review record dict."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def report_id(self) -> str:
        return self._data["report_id"]

    @property
    def validation_status(self) -> str:
        return self._data["validation_status"]

    @property
    def finalization_blocked(self) -> bool:
        return self._data["finalization_blocked"]

    @property
    def review_status(self) -> str:
        return self._data["review_status"]

    @property
    def is_final(self) -> bool:
        """True only when both validation passed AND a human approved."""
        return (
            self.validation_status == "PASS"
            and self.review_status == "approved"
        )

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_review_record(
    report_path: str | Path = "output/pader_report.json",
    report_validation_path: str | Path = "output/validation_report.json",
    dataset_validation_path: str | Path = "data/validation_report.json",
    *,
    output_path: str | Path = "output/review_record.json",
) -> ReviewRecord:
    """Initialise a pending review record from the generated report artefacts.

    This is called automatically by report_generator.run() so that a review
    record always exists alongside every generated report.
    """
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    # Load report-level validation (may not exist yet on first generation)
    report_validation: dict[str, Any] = {}
    if Path(report_validation_path).exists():
        report_validation = json.loads(
            Path(report_validation_path).read_text(encoding="utf-8")
        )

    # Load dataset validation (ingestion-level)
    dataset_validation: dict[str, Any] = {}
    if Path(dataset_validation_path).exists():
        dataset_validation = json.loads(
            Path(dataset_validation_path).read_text(encoding="utf-8")
        )

    validation_status: str = report_validation.get("status", "UNKNOWN")
    finalization_blocked: bool = validation_status != "PASS"

    section_names = [s["section_name"] for s in report.get("sections", [])]

    record_data: dict[str, Any] = {
        "review_version": REVIEW_VERSION,
        "report_id": str(uuid.uuid4()),
        "report_path": str(Path(report_path)),
        "report_generation_timestamp": report.get("generation_timestamp", ""),
        "model_name": report.get("model_name", ""),
        "prompt_version": report.get("prompt_version", ""),
        # Validation snapshots (referenced by the UI; not modified during review)
        "validation_status": validation_status,
        "finalization_blocked": finalization_blocked,
        "report_validation_errors": report_validation.get("errors", []),
        "report_validation_warnings": report_validation.get("warnings", []),
        "report_numeric_claims_checked": report_validation.get("numeric_claims_checked", 0),
        "report_numeric_claims_failed": report_validation.get("numeric_claims_failed", 0),
        "dataset_validation_status": _dataset_status(dataset_validation),
        "dataset_validation_warnings": dataset_validation.get("warnings", []),
        "dataset_validation_errors": dataset_validation.get("errors", []),
        "dataset_row_count": dataset_validation.get("input_rows", None),
        "dataset_unique_cases": dataset_validation.get("unique_cases", None),
        # Reviewer decision (populated by submit_review)
        "review_status": "pending",
        "reviewer": None,
        "timestamp": None,
        "comments": "",
        "approved_sections": [],
        "flagged_sections": [],
        # Section roster (for per-section tracking)
        "section_names": section_names,
    }

    record = ReviewRecord(record_data)
    save_review_record(record, output_path)
    return record


def _dataset_status(dataset_validation: dict[str, Any]) -> str:
    """Derive a human-readable dataset validation status."""
    if not dataset_validation:
        return "UNKNOWN"
    errors = dataset_validation.get("errors", [])
    return "FAIL" if errors else "PASS"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_review_record(record: ReviewRecord, path: str | Path = "output/review_record.json") -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_review_record(path: str | Path = "output/review_record.json") -> ReviewRecord:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_record_schema(data)
    return ReviewRecord(data)


def _validate_record_schema(data: dict[str, Any]) -> None:
    required = {
        "review_version", "report_id", "validation_status",
        "review_status", "approved_sections", "flagged_sections",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"Review record is missing required fields: {sorted(missing)}")


# ---------------------------------------------------------------------------
# Review actions
# ---------------------------------------------------------------------------


def submit_review(
    record: ReviewRecord,
    *,
    action: str,
    reviewer: str,
    comments: str = "",
    approved_sections: list[str] | None = None,
    flagged_sections: list[str] | None = None,
) -> ReviewRecord:
    """Apply a reviewer decision to a review record and return the updated record.

    Raises
    ------
    ValueError
        If *action* is not one of ``approved``, ``flagged``, ``rejected``.
    ReviewBlockedError
        If the reviewer attempts to approve a report whose validation_status
        is not ``PASS``.  An unvalidated report can never be finalised.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Invalid review action '{action}'. Must be one of: {sorted(VALID_ACTIONS)}"
        )

    if action == "approved" and record.validation_status != "PASS":
        raise ReviewBlockedError(
            f"Cannot approve report '{record.report_id}': validation_status is "
            f"'{record.validation_status}', not 'PASS'.  Resolve all validation "
            "errors before approving."
        )

    data = record.to_dict()
    data["review_status"] = action
    data["reviewer"] = reviewer.strip() if reviewer else ""
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    data["comments"] = comments
    data["approved_sections"] = list(approved_sections or [])
    data["flagged_sections"] = list(flagged_sections or [])
    # finalization_blocked reflects combined state
    data["finalization_blocked"] = not (
        data["validation_status"] == "PASS" and action == "approved"
    )
    return ReviewRecord(data)


def apply_section_action(
    record: ReviewRecord,
    *,
    section_name: str,
    action: str,  # "approve_section" | "flag_section"
) -> ReviewRecord:
    """Mark an individual section as approved or flagged."""
    if action not in {"approve_section", "flag_section"}:
        raise ValueError(f"Invalid section action: '{action}'")

    data = record.to_dict()
    approved = set(data.get("approved_sections", []))
    flagged = set(data.get("flagged_sections", []))

    if action == "approve_section":
        approved.add(section_name)
        flagged.discard(section_name)
    else:
        flagged.add(section_name)
        approved.discard(section_name)

    data["approved_sections"] = sorted(approved)
    data["flagged_sections"] = sorted(flagged)
    return ReviewRecord(data)
