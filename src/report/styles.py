"""Typography, colours, and paragraph styles for the GenAR PADER PDF."""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import TableStyle

# ── Colour palette ──────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1A2D5A")   # primary
NAVY_LIGHT = colors.HexColor("#2A4380")   # headings lighter variant
GOLD       = colors.HexColor("#C8973A")   # accent / rule lines
SLATE      = colors.HexColor("#4A5568")   # body subtext
LIGHT_GREY = colors.HexColor("#F7F8FA")   # table alt-row fill
MID_GREY   = colors.HexColor("#CBD5E0")   # table borders
CHARCOAL   = colors.HexColor("#1A202C")   # primary body text
RED_SOFT   = colors.HexColor("#C0392B")   # fatal / serious emphasis
GREEN_SOFT = colors.HexColor("#27AE60")   # recovered emphasis
WARN_BG    = colors.HexColor("#FFF3CD")   # disclaimer / warning band
WARN_BORDER= colors.HexColor("#F0AD4E")   # disclaimer border

# Chart palette (accessible, colour-blind friendly)
CHART_PALETTE = [
    colors.HexColor("#2A4380"),
    colors.HexColor("#C8973A"),
    colors.HexColor("#27AE60"),
    colors.HexColor("#C0392B"),
    colors.HexColor("#8E44AD"),
    colors.HexColor("#17A589"),
    colors.HexColor("#D35400"),
    colors.HexColor("#2C3E50"),
]


def _ps(name: str, **kwargs) -> ParagraphStyle:
    """Create a named ParagraphStyle with defaults."""
    base = {
        "fontName": "Helvetica",
        "fontSize": 10,
        "leading": 14,
        "textColor": CHARCOAL,
        "spaceAfter": 4,
    }
    base.update(kwargs)
    return ParagraphStyle(name, **base)


# ── Style catalogue ─────────────────────────────────────────────────────────
class Styles:
    cover_title = _ps(
        "cover_title",
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=36,
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    cover_product = _ps(
        "cover_product",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=24,
        textColor=GOLD,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    cover_subtitle = _ps(
        "cover_subtitle",
        fontName="Helvetica",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#B0C4DE"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    cover_meta = _ps(
        "cover_meta",
        fontName="Helvetica",
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#CBD5E0"),
        alignment=TA_LEFT,
    )
    cover_disclaimer = _ps(
        "cover_disclaimer",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#A0AEC0"),
        alignment=TA_LEFT,
    )

    # Chapter headings
    h1 = _ps(
        "h1",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=22,
        textColor=NAVY,
        spaceBefore=18,
        spaceAfter=6,
    )
    h2 = _ps(
        "h2",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=17,
        textColor=NAVY_LIGHT,
        spaceBefore=12,
        spaceAfter=4,
    )
    h3 = _ps(
        "h3",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=SLATE,
        spaceBefore=8,
        spaceAfter=3,
    )

    # Body text
    body = _ps(
        "body",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=CHARCOAL,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    body_small = _ps(
        "body_small",
        fontName="Helvetica",
        fontSize=8.5,
        leading=13,
        textColor=SLATE,
        spaceAfter=4,
    )
    footnote = _ps(
        "footnote",
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=11,
        textColor=SLATE,
        spaceAfter=2,
    )

    # Tables
    table_header = _ps(
        "table_header",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    table_cell = _ps(
        "table_cell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=CHARCOAL,
    )
    table_cell_center = _ps(
        "table_cell_center",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=CHARCOAL,
        alignment=TA_CENTER,
    )
    table_cell_right = _ps(
        "table_cell_right",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=CHARCOAL,
        alignment=TA_RIGHT,
    )
    table_cell_bold = _ps(
        "table_cell_bold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=CHARCOAL,
    )

    # Evidence / traceability
    ev_id = _ps(
        "ev_id",
        fontName="Courier",
        fontSize=7.5,
        leading=11,
        textColor=NAVY_LIGHT,
    )
    ev_label = _ps(
        "ev_label",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=12,
        textColor=NAVY,
    )

    caption = _ps(
        "caption",
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=12,
        textColor=SLATE,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=8,
    )

    page_header_text = _ps(
        "page_header_text",
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=SLATE,
    )
    page_footer_text = _ps(
        "page_footer_text",
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=SLATE,
        alignment=TA_CENTER,
    )


# ── Reusable TableStyle factories ───────────────────────────────────────────
def standard_table_style(
    header_bg: colors.Color = NAVY,
    alt_row_bg: colors.Color = LIGHT_GREY,
    border_color: colors.Color = MID_GREY,
) -> TableStyle:
    return TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8.5),
        ("LEADING",       (0, 0), (-1, 0),  12),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
        ("TOPPADDING",    (0, 0), (-1, 0),  6),
        ("ALIGN",         (0, 0), (-1, 0),  "CENTER"),
        # Body
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8.5),
        ("LEADING",       (0, 1), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        # Alt rows
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, alt_row_bg]),
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.4, border_color),
        ("LINEBELOW",     (0, 0), (-1, 0),  1.0, GOLD),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])


def evidence_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#EBF0FB")),
        ("FONTNAME",      (0, 0), (0, -1), "Courier-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7.5),
        ("LEADING",       (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.3, MID_GREY),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F7FF")]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ])
