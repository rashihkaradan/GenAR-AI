"""Reusable ReportLab Platypus table builders for the PADER PDF."""
from __future__ import annotations

import textwrap
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table

from .styles import (
    MID_GREY,
    NAVY,
    GOLD,
    LIGHT_GREY,
    SLATE,
    Styles,
    standard_table_style,
    evidence_table_style,
)


# ── Helper ───────────────────────────────────────────────────────────────────

def _p(text: str, style=None) -> Paragraph:
    if style is None:
        style = Styles.table_cell
    return Paragraph(str(text), style)


def _pc(text: str) -> Paragraph:
    return Paragraph(str(text), Styles.table_cell_center)


def _pr(text: str) -> Paragraph:
    return Paragraph(str(text), Styles.table_cell_right)


def _ph(text: str) -> Paragraph:
    return Paragraph(str(text), Styles.table_header)


# ── 1. Case Summary table ────────────────────────────────────────────────────

def case_summary_table(case_summary: dict[str, Any]) -> Table:
    headers = [_ph("Metric"), _ph("Value"), _ph("Unit"), _ph("Calculation")]
    rows = [headers]
    items = [
        ("Total Cases",          "total_cases"),
        ("Serious Cases",        "serious_cases"),
        ("Non-Serious Cases",    "non_serious_cases"),
        ("Serious Case %",       "serious_case_percentage"),
    ]
    for label, key in items:
        entry = case_summary.get(key, {})
        rows.append([
            _p(label, Styles.table_cell_bold),
            _pc(str(entry.get("value", "—"))),
            _pc(str(entry.get("unit", ""))),
            _p(str(entry.get("calculation", ""))[:80]),
        ])
    col_widths = [55 * mm, 28 * mm, 30 * mm, 72 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 2. Demographics summary table ────────────────────────────────────────────

def demographics_table(
    age_data: list[dict[str, Any]],
    sex_data: list[dict[str, Any]],
    col_width: float = 185 * mm,
) -> Table:
    headers = [_ph("Category"), _ph("Sub-Group"), _ph("Count"), _ph("% of Cases")]
    rows = [headers]
    total_age = sum(r["count"] for r in age_data) or 1
    for row in age_data:
        pct = 100 * row["count"] / total_age
        rows.append([_p("Age Group"), _p(row["category"].title()),
                     _pc(str(row["count"])), _pc(f"{pct:.1f}%")])

    total_sex = sum(r["count"] for r in sex_data) or 1
    for row in sex_data:
        pct = 100 * row["count"] / total_sex
        rows.append([_p("Sex"), _p(row["category"].title()),
                     _pc(str(row["count"])), _pc(f"{pct:.1f}%")])

    col_widths = [40 * mm, 60 * mm, 35 * mm, 50 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 3. Reaction frequency table ──────────────────────────────────────────────

def reaction_frequency_table(
    reaction_counts: list[dict[str, Any]],
    top_n: int = 20,
    title_col: str = "Preferred Term",
) -> Table:
    data = reaction_counts[:top_n]
    total = sum(r["count"] for r in data) or 1
    headers = [_ph("#"), _ph(title_col), _ph("Count"), _ph("% of Top PT")]
    rows = [headers]
    for rank, r in enumerate(data, 1):
        pct = 100 * r["count"] / total
        rows.append([
            _pc(str(rank)),
            _p(r["reaction"]),
            _pc(str(r["count"])),
            _pc(f"{pct:.1f}%"),
        ])
    col_widths = [12 * mm, 120 * mm, 25 * mm, 30 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 4. Outcome distribution table ────────────────────────────────────────────

_OUTCOME_DISPLAY = {
    "recovered_resolved":             "Recovered / Resolved",
    "recovering_resolving":           "Recovering / Resolving",
    "not_recovered_not_resolved_ongoing": "Not Recovered / Ongoing",
    "unknown":                        "Unknown",
    "recovered_resolved_with_sequelae": "Resolved with Sequelae",
    "fatal":                          "Fatal",
}


def outcome_table(outcome_data: list[dict[str, Any]]) -> Table:
    total = sum(r["count"] for r in outcome_data) or 1
    headers = [_ph("Outcome"), _ph("Instance Count"), _ph("% of Instances")]
    rows = [headers]
    for r in outcome_data:
        label = _OUTCOME_DISPLAY.get(r["outcome"], r["outcome"])
        pct = 100 * r["count"] / total
        rows.append([_p(label), _pc(str(r["count"])), _pc(f"{pct:.1f}%")])
    col_widths = [100 * mm, 45 * mm, 45 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    ts = standard_table_style()
    # Highlight fatal row
    for i, r in enumerate(outcome_data, 1):
        if r["outcome"] == "fatal":
            ts.add("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#C0392B"))
            ts.add("FONTNAME",  (0, i), (-1, i), "Helvetica-Bold")
    t.setStyle(ts)
    return t


# ── 5. Country distribution table (top N) ───────────────────────────────────

def country_table(
    country_data: list[dict[str, Any]],
    top_n: int = 15,
) -> Table:
    data = country_data[:top_n]
    total = sum(r["count"] for r in country_data) or 1
    headers = [_ph("#"), _ph("Occurrence Country"), _ph("Case Count"), _ph("% of Cases")]
    rows = [headers]
    for rank, r in enumerate(data, 1):
        pct = 100 * r["count"] / total
        rows.append([
            _pc(str(rank)),
            _p(r["category"].title()),
            _pc(str(r["count"])),
            _pc(f"{pct:.1f}%"),
        ])
    col_widths = [12 * mm, 100 * mm, 40 * mm, 38 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 6. Case index listing table (paginated sub-set) ──────────────────────────

def case_index_table(
    case_index: list[dict[str, Any]],
    max_rows: int = 50,
) -> Table:
    """Render the first max_rows entries of the case index as a table."""
    subset = case_index[:max_rows]
    headers = [
        _ph("Row"), _ph("Case ID"), _ph("Reaction PT(s)"),
        _ph("Serious"), _ph("Received"), _ph("Country"), _ph("Outcome"),
    ]
    rows = [headers]
    for row in subset:
        pt = str(row.get("reaction_preferred_terms", ""))
        if len(pt) > 60:
            pt = pt[:58] + "…"
        rows.append([
            _pc(str(row.get("source_row_number", ""))),
            _p(str(row.get("case_id", ""))),
            _p(pt),
            _pc(str(row.get("seriousness", ""))),
            _pc(str(row.get("received_date", ""))),
            _pc(str(row.get("country", ""))),
            _p(str(row.get("outcome", ""))),
        ])
    col_widths = [10 * mm, 26 * mm, 55 * mm, 18 * mm, 22 * mm, 20 * mm, 34 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 7. Alert summary table ───────────────────────────────────────────────────

def alert_summary_table(alerts: dict[str, Any]) -> Table:
    headers = [_ph("Metric"), _ph("Value")]
    rows = [headers]
    items = [
        ("Alert Cases (Expedited Criterion)",
         str(alerts.get("alert_cases", {}).get("value", "—"))),
        ("Alert Cases with Fatal Outcome Recorded",
         str(alerts.get("fatal_outcome_recorded_cases", {}).get("value", "—"))),
        ("Alert Cases Without Recorded Fatal Outcome",
         str(alerts.get("cases_without_recorded_fatal_outcome", {}).get("value", "—"))),
        ("Expectedness Assessment", "Not assessed — no product label/CCDS supplied"),
    ]
    for label, val in items:
        rows.append([_p(label, Styles.table_cell_bold), _p(val)])
    col_widths = [120 * mm, 65 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 8. Monthly trend table ───────────────────────────────────────────────────

def monthly_trend_table(
    cases_by_month: list[dict[str, Any]],
    serious_by_month: list[dict[str, Any]],
) -> Table:
    serious_map = {r["month"]: r["count"] for r in serious_by_month}
    headers = [_ph("Reporting Month"), _ph("All Cases"), _ph("Serious Cases"), _ph("Non-Serious")]
    rows = [headers]
    for row in cases_by_month:
        month = row["month"]
        total = row["count"]
        serious = serious_map.get(month, 0)
        nonsrious = total - serious
        rows.append([
            _pc(month),
            _pc(str(total)),
            _pc(str(serious)),
            _pc(str(nonsrious)),
        ])
    col_widths = [50 * mm, 45 * mm, 45 * mm, 45 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(standard_table_style())
    return t


# ── 9. Evidence appendix table ───────────────────────────────────────────────

def evidence_appendix_table(
    evidence_items: list[dict[str, Any]],
    max_items: int | None = None,
) -> Table:
    items = evidence_items[:max_items] if max_items else evidence_items
    headers = [_ph("Evidence ID"), _ph("Source Field(s)"), _ph("Value / Summary"), _ph("Analysis Level")]
    rows = [headers]
    for item in items:
        ev_id = item.get("evidence_id", "")
        src = ", ".join(item.get("source_fields", []))[:60]
        val = item.get("value", "")
        if isinstance(val, (dict, list)):
            import json
            val_str = json.dumps(val, ensure_ascii=False)
        else:
            val_str = str(val)
        val_str = val_str[:120] + ("…" if len(val_str) > 120 else "")
        level = str(item.get("analysis_level", ""))
        rows.append([
            Paragraph(ev_id, Styles.ev_id),
            _p(src, Styles.body_small),
            _p(val_str, Styles.body_small),
            _pc(level),
        ])
    col_widths = [32 * mm, 45 * mm, 85 * mm, 23 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(evidence_table_style())
    return t
