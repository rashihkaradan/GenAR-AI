"""ReportLab chart builders using deterministic analysis_results.json data only.

All functions accept plain Python dicts extracted from analysis_results.json and
return a ReportLab Drawing that can be placed directly in a Platypus story.
"""
from __future__ import annotations

from typing import Any

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, Group, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import mm

from .styles import (
    CHART_PALETTE,
    GOLD,
    LIGHT_GREY,
    MID_GREY,
    NAVY,
    NAVY_LIGHT,
    SLATE,
)

# ── Shared helpers ──────────────────────────────────────────────────────────

_LABEL_FONT  = "Helvetica"
_LABEL_BOLD  = "Helvetica-Bold"
_LABEL_SIZE  = 7.5
_TITLE_SIZE  = 9
_AXIS_SIZE   = 7


def _titled_drawing(width: float, height: float, title: str) -> tuple[Drawing, float]:
    """Return (drawing, y_offset) leaving space for the title at the top."""
    d = Drawing(width, height)
    title_h = 16
    d.add(String(
        width / 2, height - title_h + 2,
        title,
        fontName=_LABEL_BOLD,
        fontSize=_TITLE_SIZE,
        fillColor=NAVY,
        textAnchor="middle",
    ))
    return d, height - title_h - 4


def _truncate(text: str, max_len: int = 28) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def _note(d: Drawing, x: float, y: float, text: str) -> None:
    d.add(String(
        x, y, text,
        fontName="Helvetica-Oblique",
        fontSize=6.5,
        fillColor=SLATE,
        textAnchor="start",
    ))


# ── 1. Serious vs Non-Serious pie ───────────────────────────────────────────

def serious_vs_nonserious_chart(
    case_summary: dict[str, Any],
    width: float = 160 * mm,
    height: float = 80 * mm,
) -> Drawing:
    serious = case_summary.get("serious_cases", {}).get("value", 0)
    nonserious = case_summary.get("non_serious_cases", {}).get("value", 0)
    total = serious + nonserious or 1

    d, oy = _titled_drawing(width, height, "Case Seriousness Distribution")

    chart_w = 70 * mm
    chart_h = 60 * mm
    pie = Pie()
    pie.x = 10 * mm
    pie.y = oy - chart_h
    pie.width  = chart_w
    pie.height = chart_h
    pie.data   = [serious, nonserious] if nonserious > 0 else [serious, 0.001]
    pie.labels = [
        f"Serious\n{serious} ({100*serious/total:.1f}%)",
        f"Non-Serious\n{nonserious} ({100*nonserious/total:.1f}%)",
    ]
    pie.slices[0].fillColor = colors.HexColor("#C0392B")
    pie.slices[1].fillColor = colors.HexColor("#27AE60")
    pie.slices[0].labelRadius = 1.25
    pie.slices[1].labelRadius = 1.25
    pie.sideLabels = True
    pie.slices.fontSize = _LABEL_SIZE
    pie.slices.fontName = _LABEL_FONT
    pie.simpleLabels = False
    d.add(pie)

    # Legend
    lx = chart_w + 20 * mm
    ly = oy - 12 * mm
    for i, (label, col) in enumerate([("Serious", colors.HexColor("#C0392B")),
                                        ("Non-Serious", colors.HexColor("#27AE60"))]):
        d.add(Rect(lx, ly - i * 14, 10, 10, fillColor=col, strokeColor=col))
        d.add(String(lx + 14, ly - i * 14 + 1, label,
                     fontName=_LABEL_FONT, fontSize=_LABEL_SIZE, fillColor=SLATE))
    return d


# ── 2. Top-N Reactions horizontal bar ───────────────────────────────────────

def top_reactions_chart(
    reaction_counts: list[dict[str, Any]],
    top_n: int = 12,
    width: float = 170 * mm,
    height: float = 110 * mm,
) -> Drawing:
    data = reaction_counts[:top_n]
    labels = [_truncate(r["reaction"]) for r in data]
    values = [r["count"] for r in data]

    d, oy = _titled_drawing(width, height, f"Top {len(data)} Reported Preferred Terms")

    chart_h = oy - 8
    chart_w = width - 75 * mm

    chart = HorizontalBarChart()
    chart.x = 65 * mm
    chart.y = 8
    chart.width  = chart_w
    chart.height = chart_h
    chart.data   = [values]
    chart.categoryAxis.categoryNames = labels[::-1]  # largest at top
    chart.categoryAxis.labels.fontName  = _LABEL_FONT
    chart.categoryAxis.labels.fontSize  = _AXIS_SIZE
    chart.categoryAxis.labels.textAnchor = "end"
    chart.categoryAxis.labels.dx = -3
    chart.valueAxis.labels.fontName = _LABEL_FONT
    chart.valueAxis.labels.fontSize = _AXIS_SIZE
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.1
    chart.bars[0].fillColor  = NAVY
    chart.bars[0].strokeColor = colors.white
    chart.bars[0].strokeWidth = 0.3
    chart.barSpacing = 1
    chart.groupSpacing = 2
    d.add(chart)

    # Value labels at bar end
    max_v = max(values) or 1
    for i, v in enumerate(values[::-1]):
        bar_x = chart.x + (v / max_v) * chart_w
        bar_y = chart.y + (chart_h / len(values)) * i + (chart_h / len(values)) * 0.3
        d.add(String(bar_x + 3, bar_y, str(v),
                     fontName=_LABEL_FONT, fontSize=6.5, fillColor=SLATE))
    return d


# ── 3. Age-Group bar chart ───────────────────────────────────────────────────

def age_group_chart(
    age_data: list[dict[str, Any]],
    width: float = 140 * mm,
    height: float = 80 * mm,
) -> Drawing:
    # Exclude missing from bars but keep in label
    display = [r for r in age_data if r["category"] != "missing"]
    labels = [r["category"] for r in display]
    values = [r["count"] for r in display]

    d, oy = _titled_drawing(width, height, "Age-Group Distribution (Cases)")

    chart = VerticalBarChart()
    chart.x = 12 * mm
    chart.y = 16
    chart.width  = width - 20 * mm
    chart.height = oy - 20
    chart.data   = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = _LABEL_FONT
    chart.categoryAxis.labels.fontSize = _AXIS_SIZE
    chart.categoryAxis.labels.angle = 15
    chart.categoryAxis.labels.dy = -6
    chart.valueAxis.labels.fontName = _LABEL_FONT
    chart.valueAxis.labels.fontSize = _AXIS_SIZE
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.15 if values else 10
    chart.bars[0].fillColor  = NAVY_LIGHT
    chart.bars[0].strokeColor = colors.white
    chart.bars[0].strokeWidth = 0.3
    d.add(chart)
    return d


# ── 4. Sex distribution pie ──────────────────────────────────────────────────

def sex_distribution_chart(
    sex_data: list[dict[str, Any]],
    width: float = 130 * mm,
    height: float = 75 * mm,
) -> Drawing:
    palette = [colors.HexColor("#2A4380"), colors.HexColor("#C8973A"),
               colors.HexColor("#CBD5E0")]
    display = [r for r in sex_data if r["count"] > 0]
    total = sum(r["count"] for r in display) or 1

    d, oy = _titled_drawing(width, height, "Sex Distribution (Cases)")

    chart_r = min(oy, width) * 0.38
    pie = Pie()
    pie.x = width / 2 - chart_r
    pie.y = oy - chart_r * 2
    pie.width  = chart_r * 2
    pie.height = chart_r * 2
    pie.data   = [r["count"] for r in display]
    pie.labels = [
        f"{r['category'].title()}\n{r['count']} ({100*r['count']/total:.0f}%)"
        for r in display
    ]
    for i, row in enumerate(display):
        pie.slices[i].fillColor = palette[i % len(palette)]
    pie.sideLabels = True
    pie.slices.fontSize  = _LABEL_SIZE
    pie.slices.fontName  = _LABEL_FONT
    pie.simpleLabels = False
    d.add(pie)
    return d


# ── 5. Country distribution horizontal bar (top 10) ─────────────────────────

def country_distribution_chart(
    country_data: list[dict[str, Any]],
    top_n: int = 10,
    width: float = 160 * mm,
    height: float = 90 * mm,
) -> Drawing:
    data = [r for r in country_data if r["category"] != "missing"][:top_n]
    labels = [r["category"].title() for r in data]
    values = [r["count"] for r in data]

    d, oy = _titled_drawing(width, height, f"Top {len(data)} Occurrence Countries (Cases)")

    chart = HorizontalBarChart()
    chart.x = 38 * mm
    chart.y = 8
    chart.width  = width - 44 * mm
    chart.height = oy - 12
    chart.data   = [values]
    chart.categoryAxis.categoryNames = labels[::-1]
    chart.categoryAxis.labels.fontName  = _LABEL_FONT
    chart.categoryAxis.labels.fontSize  = _AXIS_SIZE
    chart.categoryAxis.labels.textAnchor = "end"
    chart.categoryAxis.labels.dx = -3
    chart.valueAxis.labels.fontName = _LABEL_FONT
    chart.valueAxis.labels.fontSize = _AXIS_SIZE
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.1 if values else 10
    chart.bars[0].fillColor  = colors.HexColor("#17A589")
    chart.bars[0].strokeColor = colors.white
    chart.bars[0].strokeWidth = 0.3
    d.add(chart)
    return d


# ── 6. Outcome distribution bar ─────────────────────────────────────────────

_OUTCOME_COLORS = {
    "recovered_resolved":             colors.HexColor("#27AE60"),
    "recovering_resolving":           colors.HexColor("#58D68D"),
    "not_recovered_not_resolved_ongoing": colors.HexColor("#F39C12"),
    "unknown":                        colors.HexColor("#95A5A6"),
    "recovered_resolved_with_sequelae": colors.HexColor("#D4AC0D"),
    "fatal":                          colors.HexColor("#C0392B"),
}

_OUTCOME_LABELS = {
    "recovered_resolved":             "Recovered/Resolved",
    "recovering_resolving":           "Recovering/Resolving",
    "not_recovered_not_resolved_ongoing": "Ongoing",
    "unknown":                        "Unknown",
    "recovered_resolved_with_sequelae": "Resolved w/ Sequelae",
    "fatal":                          "Fatal",
}


def outcome_distribution_chart(
    outcome_data: list[dict[str, Any]],
    width: float = 160 * mm,
    height: float = 80 * mm,
) -> Drawing:
    labels = [_OUTCOME_LABELS.get(r["outcome"], r["outcome"]) for r in outcome_data]
    values = [r["count"] for r in outcome_data]
    fill_colors = [_OUTCOME_COLORS.get(r["outcome"], NAVY) for r in outcome_data]

    d, oy = _titled_drawing(width, height, "Reaction Outcome Distribution")

    chart = HorizontalBarChart()
    chart.x = 45 * mm
    chart.y = 8
    chart.width  = width - 52 * mm
    chart.height = oy - 12
    chart.data   = [values]
    chart.categoryAxis.categoryNames = labels[::-1]
    chart.categoryAxis.labels.fontName  = _LABEL_FONT
    chart.categoryAxis.labels.fontSize  = _AXIS_SIZE
    chart.categoryAxis.labels.textAnchor = "end"
    chart.categoryAxis.labels.dx = -3
    chart.valueAxis.labels.fontName = _LABEL_FONT
    chart.valueAxis.labels.fontSize = _AXIS_SIZE
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.1 if values else 10
    chart.bars[0].fillColor  = NAVY_LIGHT
    chart.bars[0].strokeColor = colors.white
    chart.bars[0].strokeWidth = 0.3
    d.add(chart)
    return d


# ── 7. Monthly trend line chart ──────────────────────────────────────────────

def monthly_trend_chart(
    cases_by_month: list[dict[str, Any]],
    serious_by_month: list[dict[str, Any]],
    width: float = 175 * mm,
    height: float = 90 * mm,
) -> Drawing:
    month_labels = [r["month"] for r in cases_by_month]
    total_vals   = [(i + 1, r["count"]) for i, r in enumerate(cases_by_month)]
    serious_vals = [(i + 1, r["count"]) for i, r in enumerate(serious_by_month)]
    n = len(cases_by_month)

    d, oy = _titled_drawing(width, height, "Monthly Case Trend (All Cases vs Serious Cases)")

    chart = LinePlot()
    chart.x = 14 * mm
    chart.y = 18
    chart.width  = width - 20 * mm
    chart.height = oy - 22
    chart.data   = [total_vals, serious_vals]
    chart.lines[0].strokeColor = NAVY
    chart.lines[0].strokeWidth = 1.5
    chart.lines[0].symbol = None
    chart.lines[1].strokeColor = colors.HexColor("#C0392B")
    chart.lines[1].strokeWidth = 1.0
    chart.lines[1].strokeDashArray = [3, 2]
    chart.lines[1].symbol = None
    chart.xValueAxis.valueMin = 1
    chart.xValueAxis.valueMax = n
    chart.xValueAxis.valueStep = 1
    chart.xValueAxis.labels.fontName = _LABEL_FONT
    chart.xValueAxis.labels.fontSize = 6
    chart.xValueAxis.labels.angle    = 35
    chart.xValueAxis.labels.dy       = -8
    chart.yValueAxis.valueMin = 0
    chart.yValueAxis.valueMax = max(r["count"] for r in cases_by_month) * 1.15
    chart.yValueAxis.labels.fontName = _LABEL_FONT
    chart.yValueAxis.labels.fontSize = _AXIS_SIZE
    d.add(chart)

    # X-axis month labels
    step_x = chart.width / max(n - 1, 1)
    for i, label in enumerate(month_labels):
        d.add(String(
            chart.x + i * step_x,
            8,
            label[5:],            # show MM only to save space
            fontName=_LABEL_FONT,
            fontSize=6,
            fillColor=SLATE,
            textAnchor="middle",
        ))

    # Legend
    lx = chart.x + chart.width - 55 * mm
    ly = chart.y + chart.height - 5
    for i, (label, col, dash) in enumerate([
        ("All Cases", NAVY, None),
        ("Serious Cases", colors.HexColor("#C0392B"), [3, 2]),
    ]):
        d.add(Line(lx, ly - i * 12 + 3, lx + 20, ly - i * 12 + 3,
                   strokeColor=col, strokeWidth=1.5,
                   strokeDashArray=dash))
        d.add(String(lx + 24, ly - i * 12, label,
                     fontName=_LABEL_FONT, fontSize=7, fillColor=SLATE))

    _note(d, chart.x, 1,
          "Observed counts; not safety-signal determinations.")
    return d
