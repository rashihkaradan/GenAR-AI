"""Tests for the human review stage (src/review/)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.review.review_store import (
    ReviewBlockedError,
    ReviewRecord,
    apply_section_action,
    create_review_record,
    load_review_record,
    save_review_record,
    submit_review,
)
from src.review.finalize import finalize


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_REPORT: dict = {
    "report_type": "PADER-style report",
    "generation_timestamp": "2026-08-15T12:00:00+00:00",
    "model_name": "deterministic-evidence-template-fallback",
    "prompt_version": "1.0.0",
    "evidence_source": "evidence.json",
    "sections": [
        {
            "section_name": "Reporting Period",
            "generated_content": "Reporting period: 2024-12-27 to 2025-12-26.",
            "evidence_ids": ["EV-PERIOD-001"],
            "generation_timestamp": "2026-08-15T12:00:00+00:00",
            "model_name": "deterministic-evidence-template",
            "prompt_version": "1.0.0",
        },
        {
            "section_name": "Narrative Summary and Analysis",
            "generated_content": "Summary text.",
            "evidence_ids": ["EV-CASE-001"],
            "generation_timestamp": "2026-08-15T12:00:00+00:00",
            "model_name": "deterministic-evidence-template-fallback",
            "prompt_version": "1.0.0",
        },
    ],
}

_PASS_VALIDATION: dict = {
    "status": "PASS",
    "finalization_status": "eligible_for_human_review",
    "numeric_claims_checked": 10,
    "numeric_claims_failed": 0,
    "evidence_references_checked": 5,
    "missing_evidence": [],
    "errors": [],
    "warnings": [],
}

_FAIL_VALIDATION: dict = {
    "status": "FAIL",
    "finalization_status": "blocked_pending_human_review",
    "numeric_claims_checked": 10,
    "numeric_claims_failed": 2,
    "evidence_references_checked": 5,
    "missing_evidence": [],
    "errors": [{"code": "numeric_mismatch", "section": "Reporting Period", "detail": "1024 != 999"}],
    "warnings": [],
}

_DATASET_VALIDATION: dict = {
    "input_rows": 1068,
    "valid_rows": 1068,
    "invalid_rows": 0,
    "unique_cases": 1024,
    "errors": [],
    "warnings": [{"code": "unexpected_age_unit", "count": 3}],
}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _setup_files(tmpdir: Path, *, validation: dict = _PASS_VALIDATION) -> tuple[Path, Path, Path, Path]:
    report_path = tmpdir / "output" / "pader_report.json"
    report_val_path = tmpdir / "output" / "validation_report.json"
    dataset_val_path = tmpdir / "data" / "validation_report.json"
    review_path = tmpdir / "output" / "review_record.json"
    _write_json(report_path, _MINIMAL_REPORT)
    _write_json(report_val_path, validation)
    _write_json(dataset_val_path, _DATASET_VALIDATION)
    return report_path, report_val_path, dataset_val_path, review_path


# ---------------------------------------------------------------------------
# create_review_record
# ---------------------------------------------------------------------------

class TestCreateReviewRecord:
    def test_creates_pending_record(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        record = create_review_record(
            report_path=report_path,
            report_validation_path=rval,
            dataset_validation_path=dval,
            output_path=review_path,
        )
        assert record.review_status == "pending"
        assert record.validation_status == "PASS"
        assert not record.is_final

    def test_persists_to_disk(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        create_review_record(report_path=report_path, report_validation_path=rval,
                             dataset_validation_path=dval, output_path=review_path)
        assert review_path.exists()
        data = json.loads(review_path.read_text(encoding="utf-8"))
        assert data["review_status"] == "pending"

    def test_fail_validation_sets_blocked(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir, validation=_FAIL_VALIDATION)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        assert record.validation_status == "FAIL"
        assert record.finalization_blocked

    def test_missing_validation_files_handled_gracefully(self, tmpdir):
        report_path = tmpdir / "output" / "pader_report.json"
        review_path = tmpdir / "output" / "review_record.json"
        _write_json(report_path, _MINIMAL_REPORT)
        # No validation files exist
        record = create_review_record(
            report_path=report_path,
            report_validation_path=tmpdir / "nonexistent_rval.json",
            dataset_validation_path=tmpdir / "nonexistent_dval.json",
            output_path=review_path,
        )
        assert record.validation_status == "UNKNOWN"
        assert record.finalization_blocked  # unknown is not PASS

    def test_section_roster_populated(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        assert "Reporting Period" in record.to_dict()["section_names"]
        assert "Narrative Summary and Analysis" in record.to_dict()["section_names"]


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------

class TestReviewRecordRoundTrip:
    def test_round_trip(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        original = create_review_record(report_path=report_path, report_validation_path=rval,
                                        dataset_validation_path=dval, output_path=review_path)
        loaded = load_review_record(review_path)
        assert loaded.report_id == original.report_id
        assert loaded.validation_status == original.validation_status
        assert loaded.review_status == original.review_status

    def test_load_invalid_record_raises(self, tmpdir):
        bad_path = tmpdir / "bad.json"
        _write_json(bad_path, {"not_a_valid_record": True})
        with pytest.raises(ValueError, match="missing required fields"):
            load_review_record(bad_path)


# ---------------------------------------------------------------------------
# submit_review — whole-report actions
# ---------------------------------------------------------------------------

class TestSubmitReview:
    def _make_pass_record(self, tmpdir) -> ReviewRecord:
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        return create_review_record(report_path=report_path, report_validation_path=rval,
                                    dataset_validation_path=dval, output_path=review_path)

    def _make_fail_record(self, tmpdir) -> ReviewRecord:
        report_path, rval, dval, review_path = _setup_files(tmpdir, validation=_FAIL_VALIDATION)
        return create_review_record(report_path=report_path, report_validation_path=rval,
                                    dataset_validation_path=dval, output_path=review_path)

    def test_unvalidated_report_cannot_be_approved(self, tmpdir):
        record = self._make_fail_record(tmpdir)
        with pytest.raises(ReviewBlockedError):
            submit_review(record, action="approved", reviewer="Alice")

    def test_pass_report_can_be_approved(self, tmpdir):
        record = self._make_pass_record(tmpdir)
        updated = submit_review(record, action="approved", reviewer="Bob", comments="LGTM")
        assert updated.review_status == "approved"
        assert updated.is_final
        assert not updated.finalization_blocked

    def test_approved_report_embeds_reviewer_info(self, tmpdir):
        record = self._make_pass_record(tmpdir)
        updated = submit_review(record, action="approved", reviewer="Carol", comments="OK")
        d = updated.to_dict()
        assert d["reviewer"] == "Carol"
        assert d["comments"] == "OK"
        assert d["timestamp"] is not None

    def test_flag_report(self, tmpdir):
        record = self._make_pass_record(tmpdir)
        updated = submit_review(record, action="flagged", reviewer="Dave", comments="Needs rework")
        assert updated.review_status == "flagged"
        assert updated.finalization_blocked
        assert not updated.is_final

    def test_reject_report(self, tmpdir):
        record = self._make_pass_record(tmpdir)
        updated = submit_review(record, action="rejected", reviewer="Eve")
        assert updated.review_status == "rejected"
        assert updated.finalization_blocked

    def test_invalid_action_raises(self, tmpdir):
        record = self._make_pass_record(tmpdir)
        with pytest.raises(ValueError, match="Invalid review action"):
            submit_review(record, action="foobar", reviewer="Frank")

    def test_fail_report_can_be_flagged_or_rejected(self, tmpdir):
        record = self._make_fail_record(tmpdir)
        flagged = submit_review(record, action="flagged", reviewer="Grace")
        assert flagged.review_status == "flagged"
        rejected = submit_review(record, action="rejected", reviewer="Grace")
        assert rejected.review_status == "rejected"


# ---------------------------------------------------------------------------
# apply_section_action
# ---------------------------------------------------------------------------

class TestSectionAction:
    def _make_record(self, tmpdir) -> ReviewRecord:
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        return create_review_record(report_path=report_path, report_validation_path=rval,
                                    dataset_validation_path=dval, output_path=review_path)

    def test_approve_section(self, tmpdir):
        record = self._make_record(tmpdir)
        updated = apply_section_action(record, section_name="Reporting Period", action="approve_section")
        assert "Reporting Period" in updated.to_dict()["approved_sections"]
        assert "Reporting Period" not in updated.to_dict()["flagged_sections"]

    def test_flag_section(self, tmpdir):
        record = self._make_record(tmpdir)
        updated = apply_section_action(record, section_name="Reporting Period", action="flag_section")
        assert "Reporting Period" in updated.to_dict()["flagged_sections"]
        assert "Reporting Period" not in updated.to_dict()["approved_sections"]

    def test_approve_removes_from_flagged(self, tmpdir):
        record = self._make_record(tmpdir)
        flagged = apply_section_action(record, section_name="Reporting Period", action="flag_section")
        approved = apply_section_action(flagged, section_name="Reporting Period", action="approve_section")
        assert "Reporting Period" not in approved.to_dict()["flagged_sections"]
        assert "Reporting Period" in approved.to_dict()["approved_sections"]

    def test_invalid_section_action_raises(self, tmpdir):
        record = self._make_record(tmpdir)
        with pytest.raises(ValueError, match="Invalid section action"):
            apply_section_action(record, section_name="Reporting Period", action="nonsense")

    def test_multiple_sections(self, tmpdir):
        record = self._make_record(tmpdir)
        r1 = apply_section_action(record, section_name="Reporting Period", action="approve_section")
        r2 = apply_section_action(r1, section_name="Narrative Summary and Analysis", action="flag_section")
        d = r2.to_dict()
        assert "Reporting Period" in d["approved_sections"]
        assert "Narrative Summary and Analysis" in d["flagged_sections"]


# ---------------------------------------------------------------------------
# Finalize CLI
# ---------------------------------------------------------------------------

class TestFinalize:
    def test_approved_pass_report_finalizes(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        approved = submit_review(record, action="approved", reviewer="Henry")
        save_review_record(approved, review_path)

        out_path = tmpdir / "output" / "pader_report_FINAL.json"
        result = finalize(review_path=review_path, report_path=report_path, output_path=out_path)
        assert out_path.exists()
        assert result["finalization_status"] == "final"
        assert result["human_review"]["reviewer"] == "Henry"
        assert result["human_review"]["validation_status"] == "PASS"

    def test_flagged_report_cannot_be_finalized(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        flagged = submit_review(record, action="flagged", reviewer="Ivy")
        save_review_record(flagged, review_path)

        with pytest.raises(SystemExit) as exc_info:
            finalize(review_path=review_path, report_path=report_path, output_path=tmpdir / "never.json")
        assert exc_info.value.code == 1

    def test_rejected_report_cannot_be_finalized(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        rejected = submit_review(record, action="rejected", reviewer="Jack")
        save_review_record(rejected, review_path)

        with pytest.raises(SystemExit) as exc_info:
            finalize(review_path=review_path, report_path=report_path, output_path=tmpdir / "never.json")
        assert exc_info.value.code == 1

    def test_fail_validation_report_cannot_be_finalized(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir, validation=_FAIL_VALIDATION)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        save_review_record(record, review_path)

        with pytest.raises(SystemExit) as exc_info:
            finalize(review_path=review_path, report_path=report_path, output_path=tmpdir / "never.json")
        assert exc_info.value.code == 1

    def test_missing_review_record_exits(self, tmpdir):
        with pytest.raises(SystemExit) as exc_info:
            finalize(review_path=tmpdir / "nonexistent.json",
                     report_path=tmpdir / "pader_report.json",
                     output_path=tmpdir / "never.json")
        assert exc_info.value.code == 1

    def test_final_report_embeds_full_review_record(self, tmpdir):
        report_path, rval, dval, review_path = _setup_files(tmpdir)
        record = create_review_record(report_path=report_path, report_validation_path=rval,
                                      dataset_validation_path=dval, output_path=review_path)
        approved = submit_review(record, action="approved", reviewer="Kim", comments="All good",
                                 approved_sections=["Reporting Period"],
                                 flagged_sections=["Narrative Summary and Analysis"])
        save_review_record(approved, review_path)
        out_path = tmpdir / "output" / "pader_report_FINAL.json"
        result = finalize(review_path=review_path, report_path=report_path, output_path=out_path)
        hr = result["human_review"]
        assert hr["reviewer"] == "Kim"
        assert hr["comments"] == "All good"
        assert "Reporting Period" in hr["approved_sections"]
        assert "Narrative Summary and Analysis" in hr["flagged_sections"]
