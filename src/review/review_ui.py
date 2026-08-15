"""Minimal Flask review UI for PADER reports (Version 0 — no authentication).

Run with:
    python -m src.review.review_ui
or:
    flask --app src.review.review_ui run

Then open http://localhost:5000
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template_string, request

from .review_store import (
    ReviewBlockedError,
    apply_section_action,
    create_review_record,
    load_review_record,
    save_review_record,
    submit_review,
)
from ..reporting.report_generator import generate_report, LLM_SECTIONS

# ---------------------------------------------------------------------------
# Paths (configurable via env vars for flexibility)
# ---------------------------------------------------------------------------

BASE = Path(os.environ.get("GENAR_BASE", "."))
REPORT_PATH = BASE / os.environ.get("GENAR_REPORT", "output/pader_report.json")
REPORT_VALIDATION_PATH = BASE / os.environ.get("GENAR_REPORT_VALIDATION", "output/validation_report.json")
DATASET_VALIDATION_PATH = BASE / os.environ.get("GENAR_DATASET_VALIDATION", "data/validation_report.json")
EVIDENCE_PATH = BASE / os.environ.get("GENAR_EVIDENCE", "data/evidence.json")
ANALYSIS_PATH = BASE / os.environ.get("GENAR_ANALYSIS", "data/analysis_results.json")
NORMALIZED_PATH = BASE / os.environ.get("GENAR_NORMALIZED", "data/normalized_cases.jsonl")
REVIEW_RECORD_PATH = BASE / os.environ.get("GENAR_REVIEW_RECORD", "output/review_record.json")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _ensure_review_record() -> None:
    """Create a review record if it does not exist yet."""
    if not REVIEW_RECORD_PATH.exists():
        create_review_record(
            report_path=REPORT_PATH,
            report_validation_path=REPORT_VALIDATION_PATH,
            dataset_validation_path=DATASET_VALIDATION_PATH,
            output_path=REVIEW_RECORD_PATH,
        )


def _build_evidence_index(evidence: dict[str, Any]) -> dict[str, Any]:
    """Return {evidence_id: item} for fast lookup in the template."""
    return {item["evidence_id"]: item for item in evidence.get("evidence_items", [])}


# ---------------------------------------------------------------------------
# HTML template (self-contained, no external assets except Google Fonts)
# ---------------------------------------------------------------------------

_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GenAR PADER — Human Review</title>
  <meta name="description" content="Human review interface for GenAR PADER report finalization. Reviewers inspect dataset validation, analysis, report sections, and evidence before approving or flagging." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    /* ── Reset & tokens ────────────────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:         #0d1117;
      --surface:    #161b22;
      --surface-2:  #1c2230;
      --border:     #30363d;
      --border-2:   #21262d;
      --text:       #e6edf3;
      --text-muted: #8b949e;
      --text-dim:   #484f58;
      --accent:     #58a6ff;
      --accent-2:   #1f6feb;
      --green:      #3fb950;
      --green-bg:   #0d2a1a;
      --yellow:     #d29922;
      --yellow-bg:  #271d00;
      --red:        #f85149;
      --red-bg:     #2d0f0e;
      --purple:     #bc8cff;
      --purple-bg:  #1e0f33;
      --radius:     8px;
      --radius-lg:  12px;
      --shadow:     0 4px 24px rgba(0,0,0,0.4);
    }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      min-height: 100vh;
    }

    /* ── Layout ────────────────────────────────────────────────────── */
    .layout { display: flex; min-height: 100vh; }
    .sidebar {
      width: 240px;
      min-width: 240px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 24px 0;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
      flex-shrink: 0;
    }
    .sidebar-logo {
      padding: 0 20px 20px;
      border-bottom: 1px solid var(--border-2);
      margin-bottom: 16px;
    }
    .sidebar-logo span {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--text-muted);
      display: block;
      margin-top: 4px;
    }
    .sidebar-logo h1 { font-size: 18px; font-weight: 700; color: var(--accent); }
    nav a {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 20px;
      color: var(--text-muted);
      text-decoration: none;
      font-size: 13.5px;
      font-weight: 500;
      border-left: 3px solid transparent;
      transition: all .15s;
    }
    nav a:hover, nav a.active {
      color: var(--text);
      background: var(--surface-2);
      border-left-color: var(--accent);
    }
    nav .nav-icon { font-size: 15px; }
    nav .nav-section {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--text-dim);
      padding: 18px 20px 4px;
    }
    .main { flex: 1; overflow-x: hidden; }

    /* ── Top bar ───────────────────────────────────────────────────── */
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .topbar-title { font-size: 15px; font-weight: 600; }
    .topbar-meta { font-size: 12px; color: var(--text-muted); }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: .04em;
    }
    .pill-pass   { background: var(--green-bg);  color: var(--green);  border: 1px solid #2ea04340; }
    .pill-fail   { background: var(--red-bg);    color: var(--red);    border: 1px solid #f8514940; }
    .pill-warn   { background: var(--yellow-bg); color: var(--yellow); border: 1px solid #d2992240; }
    .pill-pending{ background: var(--surface-2); color: var(--text-muted); border: 1px solid var(--border); }
    .pill-approved { background: var(--green-bg);  color: var(--green);  border: 1px solid #2ea04340; }
    .pill-flagged  { background: var(--yellow-bg); color: var(--yellow); border: 1px solid #d2992240; }
    .pill-rejected { background: var(--red-bg);    color: var(--red);    border: 1px solid #f8514940; }
    .pill-unknown  { background: var(--surface-2); color: var(--text-muted); border: 1px solid var(--border); }

    /* ── Content area ──────────────────────────────────────────────── */
    .content { padding: 32px; max-width: 1100px; }

    /* ── Cards ─────────────────────────────────────────────────────── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      margin-bottom: 24px;
      overflow: hidden;
    }
    .card-header {
      padding: 16px 22px;
      border-bottom: 1px solid var(--border-2);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .card-title {
      font-size: 14px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
    }
    .card-body { padding: 20px 22px; }

    /* ── Stats row ─────────────────────────────────────────────────── */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .stat-box {
      background: var(--surface-2);
      border: 1px solid var(--border-2);
      border-radius: var(--radius);
      padding: 14px 16px;
    }
    .stat-label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
    .stat-value { font-size: 26px; font-weight: 700; color: var(--text); margin-top: 4px; }
    .stat-sub   { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

    /* ── Tables ─────────────────────────────────────────────────────── */
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em;
         color: var(--text-muted); padding: 8px 12px; text-align: left;
         border-bottom: 1px solid var(--border-2); }
    td { padding: 9px 12px; border-bottom: 1px solid var(--border-2); vertical-align: top; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: var(--surface-2); }

    /* ── Section cards ──────────────────────────────────────────────── */
    .section-card {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      margin-bottom: 14px;
      overflow: hidden;
      transition: border-color .15s;
    }
    .section-card.approved { border-color: #2ea04340; }
    .section-card.flagged  { border-color: #d2992260; }
    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 18px;
      background: var(--surface-2);
      cursor: pointer;
      gap: 12px;
      user-select: none;
    }
    .section-header:hover { background: #1e2a3a; }
    .section-name { font-weight: 600; font-size: 14px; }
    .section-body { padding: 18px; display: none; }
    .section-body.open { display: block; }
    .section-content {
      font-size: 13.5px;
      line-height: 1.7;
      color: var(--text);
      background: var(--bg);
      border: 1px solid var(--border-2);
      border-radius: var(--radius);
      padding: 14px 16px;
      margin-bottom: 14px;
      white-space: pre-wrap;
    }
    .evidence-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
    .ev-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 10px;
      background: var(--purple-bg);
      color: var(--purple);
      border: 1px solid #bc8cff30;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
      cursor: pointer;
      transition: background .1s;
    }
    .ev-chip:hover { background: #2d1a4a; }
    .evidence-detail {
      background: var(--surface-2);
      border: 1px solid var(--border-2);
      border-radius: var(--radius);
      padding: 12px 14px;
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      margin-bottom: 10px;
      display: none;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 300px;
      overflow-y: auto;
    }
    .evidence-detail.open { display: block; }
    .section-actions { display: flex; gap: 8px; flex-wrap: wrap; }

    /* ── Buttons ────────────────────────────────────────────────────── */
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: var(--radius);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all .15s;
      font-family: inherit;
    }
    .btn:disabled { opacity: .4; cursor: not-allowed; }
    .btn-primary { background: var(--accent-2); color: #fff; border-color: var(--accent); }
    .btn-primary:hover:not(:disabled) { background: #388bfd; }
    .btn-success { background: #1a4020; color: var(--green); border-color: #2ea04340; }
    .btn-success:hover:not(:disabled) { background: #1f5027; }
    .btn-warn    { background: var(--yellow-bg); color: var(--yellow); border-color: #d2992240; }
    .btn-warn:hover:not(:disabled) { background: #352300; }
    .btn-danger  { background: var(--red-bg); color: var(--red); border-color: #f8514940; }
    .btn-danger:hover:not(:disabled) { background: #3d1210; }
    .btn-ghost   { background: transparent; color: var(--text-muted); border-color: var(--border); }
    .btn-ghost:hover:not(:disabled) { background: var(--surface-2); color: var(--text); }
    .btn-sm { padding: 5px 10px; font-size: 12px; }

    /* ── Review panel ───────────────────────────────────────────────── */
    .review-panel {
      position: sticky;
      bottom: 0;
      background: var(--surface);
      border-top: 1px solid var(--border);
      padding: 20px 32px;
      z-index: 90;
      display: flex;
      align-items: flex-start;
      gap: 24px;
      flex-wrap: wrap;
    }
    .review-panel-form { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; flex: 1; min-width: 300px; }
    .form-group { display: flex; flex-direction: column; gap: 4px; }
    .form-group label { font-size: 11px; font-weight: 600; text-transform: uppercase;
                        letter-spacing: .06em; color: var(--text-muted); }
    .form-input, .form-textarea {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      color: var(--text);
      font-family: inherit;
      font-size: 13px;
      padding: 8px 12px;
      outline: none;
      transition: border-color .15s;
    }
    .form-input:focus, .form-textarea:focus { border-color: var(--accent); }
    .form-input { width: 220px; }
    .form-textarea { width: 340px; height: 52px; resize: vertical; }
    .action-btns { display: flex; gap: 8px; align-items: flex-end; flex-wrap: wrap; }

    /* ── Warnings list ──────────────────────────────────────────────── */
    .warn-list { list-style: none; }
    .warn-list li {
      display: flex;
      gap: 10px;
      padding: 9px 12px;
      border-radius: var(--radius);
      margin-bottom: 6px;
      font-size: 13px;
      background: var(--yellow-bg);
      color: var(--yellow);
      border: 1px solid #d2992220;
    }
    .err-list li {
      background: var(--red-bg);
      color: var(--red);
      border-color: #f8514920;
    }

    /* ── Toast ──────────────────────────────────────────────────────── */
    #toast {
      position: fixed;
      bottom: 120px;
      right: 28px;
      padding: 12px 20px;
      border-radius: var(--radius);
      font-size: 13.5px;
      font-weight: 600;
      z-index: 999;
      opacity: 0;
      transform: translateY(12px);
      transition: opacity .25s, transform .25s;
      pointer-events: none;
      max-width: 380px;
    }
    #toast.show { opacity: 1; transform: translateY(0); }
    #toast.success { background: var(--green-bg); color: var(--green); border: 1px solid #2ea04340; }
    #toast.error   { background: var(--red-bg);   color: var(--red);   border: 1px solid #f8514940; }
    #toast.info    { background: var(--surface-2); color: var(--accent); border: 1px solid var(--border); }

    /* ── Misc ───────────────────────────────────────────────────────── */
    .mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
    .text-muted { color: var(--text-muted); }
    hr { border: none; border-top: 1px solid var(--border-2); margin: 18px 0; }
    .blocked-banner {
      background: var(--red-bg);
      border: 1px solid #f8514940;
      border-radius: var(--radius);
      padding: 14px 18px;
      color: var(--red);
      font-size: 13.5px;
      font-weight: 600;
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .approved-banner {
      background: var(--green-bg);
      border: 1px solid #2ea04340;
      border-radius: var(--radius);
      padding: 14px 18px;
      color: var(--green);
      font-size: 13.5px;
      font-weight: 600;
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    details summary { cursor: pointer; font-weight: 600; font-size: 13px; color: var(--accent); }
    details[open] summary { margin-bottom: 10px; }
  </style>
</head>
<body>
<div class="layout">

  <!-- ── Sidebar ─────────────────────────────────────────── -->
  <aside class="sidebar">
    <div class="sidebar-logo">
      <h1>GenAR</h1>
      <span>PADER Review Console</span>
    </div>
    <nav>
      <div class="nav-section">Overview</div>
      <a href="#dataset-validation" class="nav-link"><span class="nav-icon">🗄️</span> Dataset Validation</a>
      <a href="#analysis" class="nav-link"><span class="nav-icon">📊</span> Analysis Results</a>
      <a href="#report-validation" class="nav-link"><span class="nav-icon">✅</span> Report Validation</a>
      <a href="#warnings" class="nav-link"><span class="nav-icon">⚠️</span> Warnings</a>
      <div class="nav-section">Report</div>
      <a href="#sections" class="nav-link"><span class="nav-icon">📄</span> Report Sections</a>
      <div class="nav-section">Decision</div>
      <a href="#review" class="nav-link"><span class="nav-icon">🖊️</span> Submit Review</a>
    </nav>
  </aside>

  <!-- ── Main ────────────────────────────────────────────── -->
  <div class="main">

    <!-- Top bar -->
    <div class="topbar">
      <div>
        <div class="topbar-title">Human Review — PADER Report</div>
        <div class="topbar-meta mono">{{ record.report_id[:12] }}… · Generated {{ record.report_generation_timestamp[:19].replace('T', ' ') }} UTC</div>
      </div>
      <div style="display:flex;gap:10px;align-items:center;">
        <span class="status-pill {{ 'pill-pass' if record.validation_status == 'PASS' else 'pill-fail' if record.validation_status == 'FAIL' else 'pill-unknown' }}">
          {{ '✓' if record.validation_status == 'PASS' else '✗' }} {{ record.validation_status }}
        </span>
        <span id="review-pill" class="status-pill pill-{{ record.review_status }}">
          {% if record.review_status == 'approved' %}✓{% elif record.review_status == 'flagged' %}⚑{% elif record.review_status == 'rejected' %}✗{% else %}⏳{% endif %}
          {{ record.review_status | title }}
        </span>
      </div>
    </div>

    <div class="content">

      <!-- Finalization banner -->
      {% if record.review_status == 'approved' and record.validation_status == 'PASS' %}
      <div class="approved-banner">
        ✓ This report has been approved by <strong>{{ record.reviewer }}</strong> and is eligible for finalization.
        Run <code class="mono">python -m src.review.finalize</code> to produce the FINAL report.
      </div>
      {% elif record.finalization_blocked %}
      <div class="blocked-banner">
        ✗ Finalization is blocked.
        {% if record.validation_status != 'PASS' %} Validation status is <strong>{{ record.validation_status }}</strong> — resolve all errors before approving.{% endif %}
        {% if record.review_status not in ('approved', 'pending') %} Review status: <strong>{{ record.review_status }}</strong>.{% endif %}
      </div>
      {% endif %}

      <!-- ① Dataset Validation ─────────────────────────────────────── -->
      <div id="dataset-validation" class="card">
        <div class="card-header">
          <div class="card-title">🗄️ Dataset Validation Status</div>
          <span class="status-pill {{ 'pill-pass' if record.dataset_validation_status == 'PASS' else 'pill-fail' if record.dataset_validation_status == 'FAIL' else 'pill-unknown' }}">
            {{ record.dataset_validation_status }}
          </span>
        </div>
        <div class="card-body">
          <div class="stats-grid">
            <div class="stat-box">
              <div class="stat-label">Input Rows</div>
              <div class="stat-value">{{ record.dataset_row_count or '—' }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Unique Cases</div>
              <div class="stat-value">{{ record.dataset_unique_cases or '—' }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Warnings</div>
              <div class="stat-value" style="color:var(--yellow)">{{ record.dataset_validation_warnings | length }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Errors</div>
              <div class="stat-value" style="color:var(--red)">{{ record.dataset_validation_errors | length }}</div>
            </div>
          </div>
          {% if record.dataset_validation_errors %}
          <ul class="warn-list err-list">
            {% for e in record.dataset_validation_errors %}
            <li>✗ {{ e | tojson if e is mapping else e }}</li>
            {% endfor %}
          </ul>
          {% endif %}
          {% if record.dataset_validation_warnings %}
          <ul class="warn-list">
            {% for w in record.dataset_validation_warnings %}
            <li>⚠ {{ w | tojson if w is mapping else w }}</li>
            {% endfor %}
          </ul>
          {% endif %}
          {% if not record.dataset_validation_errors and not record.dataset_validation_warnings %}
          <p class="text-muted" style="font-size:13px">No errors or warnings.</p>
          {% endif %}
        </div>
      </div>

      <!-- ② Deterministic Analysis ─────────────────────────────────── -->
      <div id="analysis" class="card">
        <div class="card-header">
          <div class="card-title">📊 Deterministic Analysis Results</div>
        </div>
        <div class="card-body">
          {% if analysis %}
          <div class="stats-grid">
            {% set cs = analysis.get('case_summary', {}) %}
            <div class="stat-box">
              <div class="stat-label">Total Cases</div>
              <div class="stat-value">{{ cs.get('total_cases', {}).get('value', '—') }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Serious</div>
              <div class="stat-value" style="color:var(--red)">{{ cs.get('serious_cases', {}).get('value', '—') }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Non-Serious</div>
              <div class="stat-value">{{ cs.get('non_serious_cases', {}).get('value', '—') }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Alert Cases</div>
              <div class="stat-value" style="color:var(--yellow)">{{ analysis.get('alerts', {}).get('alert_cases', {}).get('value', '—') }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Reaction Instances</div>
              <div class="stat-value">{{ analysis.get('reactions', {}).get('reaction_count', {}).get('value', '—') }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Period Start</div>
              <div class="stat-value" style="font-size:16px">{{ analysis.get('reporting_period', {}).get('start_date', {}).get('value', '—') }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Period End</div>
              <div class="stat-value" style="font-size:16px">{{ analysis.get('reporting_period', {}).get('end_date', {}).get('value', '—') }}</div>
            </div>
          </div>
          <details>
            <summary>Top 10 Reported Preferred Terms</summary>
            {% set top_reactions = analysis.get('reactions', {}).get('most_frequently_reported_reactions', {}).get('value', [])[:10] %}
            {% if top_reactions %}
            <table>
              <thead><tr><th>Preferred Term</th><th>Count</th></tr></thead>
              <tbody>
                {% for r in top_reactions %}
                <tr><td>{{ r.reaction }}</td><td>{{ r.count }}</td></tr>
                {% endfor %}
              </tbody>
            </table>
            {% else %}<p class="text-muted">No reaction data.</p>{% endif %}
          </details>
          {% else %}
          <p class="text-muted" style="font-size:13px">Analysis results not found. Expected at <code class="mono">data/analysis_results.json</code>.</p>
          {% endif %}
        </div>
      </div>

      <!-- ③ Report Validation ──────────────────────────────────────── -->
      <div id="report-validation" class="card">
        <div class="card-header">
          <div class="card-title">✅ Report Validation Status</div>
          <span class="status-pill {{ 'pill-pass' if record.validation_status == 'PASS' else 'pill-fail' if record.validation_status == 'FAIL' else 'pill-unknown' }}">
            {{ record.validation_status }}
          </span>
        </div>
        <div class="card-body">
          <div class="stats-grid">
            <div class="stat-box">
              <div class="stat-label">Claims Checked</div>
              <div class="stat-value">{{ record.report_numeric_claims_checked }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Claims Failed</div>
              <div class="stat-value" style="color:var(--red)">{{ record.report_numeric_claims_failed }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Errors</div>
              <div class="stat-value" style="color:var(--red)">{{ record.report_validation_errors | length }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Warnings</div>
              <div class="stat-value" style="color:var(--yellow)">{{ record.report_validation_warnings | length }}</div>
            </div>
          </div>
          {% if record.report_validation_errors %}
          <ul class="warn-list err-list" style="margin-top:12px">
            {% for e in record.report_validation_errors %}
            <li>✗ <span class="mono">{{ e | tojson if e is mapping else e }}</span></li>
            {% endfor %}
          </ul>
          {% endif %}
          {% if not record.report_validation_errors %}
          <p style="color:var(--green);font-size:13px;font-weight:600;margin-top:8px">✓ All numeric claims validated against approved evidence.</p>
          {% endif %}
        </div>
      </div>

      <!-- ④ Aggregated Warnings ────────────────────────────────────── -->
      <div id="warnings" class="card">
        <div class="card-header">
          <div class="card-title">⚠️ Warnings</div>
          {% set total_warns = (record.dataset_validation_warnings | length) + (record.report_validation_warnings | length) %}
          <span class="status-pill {{ 'pill-warn' if total_warns > 0 else 'pill-pass' }}">{{ total_warns }} warning{{ 's' if total_warns != 1 else '' }}</span>
        </div>
        <div class="card-body">
          {% if total_warns == 0 %}
          <p class="text-muted" style="font-size:13px">No warnings.</p>
          {% else %}
          {% if record.dataset_validation_warnings %}
          <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:8px">Dataset</p>
          <ul class="warn-list">
            {% for w in record.dataset_validation_warnings %}
            <li>⚠ {{ w | tojson if w is mapping else w }}</li>
            {% endfor %}
          </ul>
          {% endif %}
          {% if record.report_validation_warnings %}
          <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin:12px 0 8px">Report</p>
          <ul class="warn-list">
            {% for w in record.report_validation_warnings %}
            <li>⚠ {{ w | tojson if w is mapping else w }}</li>
            {% endfor %}
          </ul>
          {% endif %}
          {% endif %}
        </div>
      </div>

      <!-- ⑤ Report Sections ────────────────────────────────────────── -->
      <div id="sections" class="card">
        <div class="card-header">
          <div class="card-title">📄 Report Sections</div>
          <div style="font-size:12px;color:var(--text-muted)">{{ sections | length }} sections · click to expand</div>
        </div>
        <div class="card-body" style="padding: 14px 18px;">
          {% for section in sections %}
          {% set sname = section.section_name %}
          {% set is_approved = sname in record.approved_sections %}
          {% set is_flagged  = sname in record.flagged_sections %}
          {% set sec_class   = 'approved' if is_approved else 'flagged' if is_flagged else '' %}
          <div class="section-card {{ sec_class }}" id="sec-{{ loop.index }}">
            <div class="section-header" onclick="toggleSection({{ loop.index }})">
              <div style="display:flex;align-items:center;gap:10px;">
                <span style="color:var(--text-dim);font-size:12px;font-weight:600">{{ '%02d' % loop.index }}</span>
                <span class="section-name">{{ sname }}</span>
              </div>
              <div style="display:flex;align-items:center;gap:8px;">
                {% if is_approved %}
                <span class="status-pill pill-approved" style="font-size:11px;padding:3px 8px">✓ Approved</span>
                {% elif is_flagged %}
                <span class="status-pill pill-flagged" style="font-size:11px;padding:3px 8px">⚑ Flagged</span>
                {% else %}
                <span class="status-pill pill-pending" style="font-size:11px;padding:3px 8px">Pending</span>
                {% endif %}
                <span style="color:var(--text-dim)">▾</span>
              </div>
            </div>
            <div class="section-body" id="secbody-{{ loop.index }}">
              {% if section.generated_content is string %}
              <div class="section-content">{{ section.generated_content }}</div>
              {% else %}
              <div class="section-content" style="max-height:250px;overflow-y:auto">
                <em class="text-muted" style="font-size:12px">Structured listing ({{ section.generated_content | length }} rows)</em>
              </div>
              {% endif %}

              <!-- Evidence IDs -->
              <div style="margin-bottom:10px">
                <p style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:6px">Evidence IDs</p>
                <div class="evidence-chips">
                  {% for ev_id in section.evidence_ids %}
                  <span class="ev-chip" onclick="toggleEvidence('{{ loop.index }}-{{ ev_id | replace('-','_') }}')">
                    🔗 {{ ev_id }}
                  </span>
                  {% endfor %}
                </div>
                {% for ev_id in section.evidence_ids %}
                {% set ev_item = evidence_index.get(ev_id) %}
                <div class="evidence-detail" id="ev-{{ loop.index }}-{{ ev_id | replace('-','_') }}">
                  {% if ev_item %}{{ ev_item | tojson(indent=2) }}{% else %}Evidence item not found for {{ ev_id }}{% endif %}
                </div>
                {% endfor %}
              </div>

              <!-- Generation metadata -->
              <p style="font-size:11px;color:var(--text-dim);margin-bottom:12px">
                Model: <span class="mono">{{ section.model_name }}</span> ·
                Prompt v{{ section.prompt_version }} ·
                Generated {{ section.generation_timestamp[:19].replace('T',' ') }} UTC
              </p>

              <!-- Section actions -->
              <div class="section-actions">
                <button class="btn btn-success btn-sm" onclick="sectionAction('{{ sname }}', 'approve_section')">✓ Approve</button>
                <button class="btn btn-warn btn-sm" onclick="sectionAction('{{ sname }}', 'flag_section')">⚑ Flag</button>
                <button class="btn btn-ghost btn-sm" onclick="regenerateSection('{{ sname }}')">↺ Regenerate</button>
              </div>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /layout -->

<!-- ── Sticky review panel ──────────────────────────────────────────────── -->
<div id="review" class="review-panel">
  <div>
    <p style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:6px">🖊️ Submit Review Decision</p>
    <p style="font-size:12px;color:var(--text-muted)">Approval is only possible when report validation is PASS.</p>
  </div>
  <div class="review-panel-form">
    <div class="form-group">
      <label for="reviewer-name">Reviewer Name</label>
      <input id="reviewer-name" class="form-input" type="text" placeholder="Your name" value="{{ record.reviewer or '' }}" />
    </div>
    <div class="form-group">
      <label for="reviewer-comments">Comments</label>
      <textarea id="reviewer-comments" class="form-textarea" placeholder="Optional notes…">{{ record.comments or '' }}</textarea>
    </div>
    <div class="action-btns">
      <button id="btn-approve" class="btn btn-success" onclick="submitReview('approved')"
        {{ 'disabled' if record.validation_status != 'PASS' else '' }}>
        ✓ Approve
      </button>
      <button id="btn-flag" class="btn btn-warn" onclick="submitReview('flagged')">
        ⚑ Flag for Review
      </button>
      <button id="btn-reject" class="btn btn-danger" onclick="submitReview('rejected')">
        ✗ Reject Finalization
      </button>
    </div>
  </div>
</div>

<!-- Toast -->
<div id="toast"></div>

<script>
  // ── Toggle section body ───────────────────────────────────────────
  function toggleSection(idx) {
    const body = document.getElementById('secbody-' + idx);
    body.classList.toggle('open');
  }

  // ── Toggle evidence detail ────────────────────────────────────────
  function toggleEvidence(id) {
    const el = document.getElementById('ev-' + id);
    if (el) el.classList.toggle('open');
  }

  // ── Toast ─────────────────────────────────────────────────────────
  function showToast(msg, type = 'info') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'show ' + type;
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.className = ''; }, 4000);
  }

  // ── Submit whole-report review ────────────────────────────────────
  async function submitReview(action) {
    const reviewer = document.getElementById('reviewer-name').value.trim();
    if (!reviewer) { showToast('Please enter your name before submitting.', 'error'); return; }
    const comments = document.getElementById('reviewer-comments').value;
    try {
      const resp = await fetch('/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action, reviewer, comments}),
      });
      const data = await resp.json();
      if (!resp.ok) { showToast('Error: ' + (data.error || resp.status), 'error'); return; }
      showToast(data.message || 'Review submitted.', 'success');
      setTimeout(() => location.reload(), 1200);
    } catch (e) { showToast('Network error: ' + e.message, 'error'); }
  }

  // ── Per-section action ────────────────────────────────────────────
  async function sectionAction(sectionName, action) {
    try {
      const resp = await fetch('/section/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({section_name: sectionName, action}),
      });
      const data = await resp.json();
      if (!resp.ok) { showToast('Error: ' + (data.error || resp.status), 'error'); return; }
      showToast(data.message || 'Section updated.', 'success');
      setTimeout(() => location.reload(), 900);
    } catch (e) { showToast('Network error: ' + e.message, 'error'); }
  }

  // ── Regenerate section ────────────────────────────────────────────
  async function regenerateSection(sectionName) {
    showToast('Regenerating "' + sectionName + '"…', 'info');
    try {
      const resp = await fetch('/section/regenerate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({section_name: sectionName}),
      });
      const data = await resp.json();
      if (!resp.ok) { showToast('Error: ' + (data.error || resp.status), 'error'); return; }
      showToast(data.message || 'Section regenerated.', 'success');
      setTimeout(() => location.reload(), 1200);
    } catch (e) { showToast('Network error: ' + e.message, 'error'); }
  }

  // ── Sidebar active link ───────────────────────────────────────────
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        document.querySelectorAll('.nav-link').forEach(a => a.classList.remove('active'));
        const link = document.querySelector('.nav-link[href="#' + e.target.id + '"]');
        if (link) link.classList.add('active');
      }
    });
  }, {threshold: 0.4});
  document.querySelectorAll('[id]').forEach(el => observer.observe(el));
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    _ensure_review_record()
    record = load_review_record(REVIEW_RECORD_PATH)
    report = _load_json(REPORT_PATH)
    analysis = _load_json(ANALYSIS_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    evidence_index = _build_evidence_index(evidence)
    sections = report.get("sections", [])
    return render_template_string(
        _HTML,
        record=record.to_dict(),
        sections=sections,
        analysis=analysis,
        evidence_index=evidence_index,
    )


@app.route("/action", methods=["POST"])
def action():
    """Submit a whole-report review decision."""
    data = request.get_json(force=True, silent=True) or {}
    action_name = data.get("action", "")
    reviewer = data.get("reviewer", "").strip()
    comments = data.get("comments", "")

    if not reviewer:
        return jsonify({"error": "reviewer name is required"}), 400

    try:
        record = load_review_record(REVIEW_RECORD_PATH)
        updated = submit_review(
            record,
            action=action_name,
            reviewer=reviewer,
            comments=comments,
            approved_sections=record.to_dict().get("approved_sections", []),
            flagged_sections=record.to_dict().get("flagged_sections", []),
        )
        save_review_record(updated, REVIEW_RECORD_PATH)
        return jsonify({"message": f"Report {action_name}.", "review_status": action_name})
    except ReviewBlockedError as exc:
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/section/action", methods=["POST"])
def section_action():
    """Approve or flag an individual section."""
    data = request.get_json(force=True, silent=True) or {}
    section_name = data.get("section_name", "")
    action_name = data.get("action", "")
    try:
        record = load_review_record(REVIEW_RECORD_PATH)
        updated = apply_section_action(record, section_name=section_name, action=action_name)
        save_review_record(updated, REVIEW_RECORD_PATH)
        verb = "approved" if action_name == "approve_section" else "flagged"
        return jsonify({"message": f'Section "{section_name}" {verb}.'})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/section/regenerate", methods=["POST"])
def section_regenerate():
    """Regenerate a single report section and patch the live report JSON."""
    data = request.get_json(force=True, silent=True) or {}
    section_name = data.get("section_name", "")
    if not section_name:
        return jsonify({"error": "section_name is required"}), 400

    try:
        # Re-generate the full report (cheapest correct approach for the
        # deterministic fallback path; LLM path only re-calls that section
        # via the generator).
        new_report = generate_report(
            evidence_path=EVIDENCE_PATH,
            analysis_path=ANALYSIS_PATH,
            normalized_path=NORMALIZED_PATH,
        )
        existing = _load_json(REPORT_PATH)
        new_section = next(
            (s for s in new_report["sections"] if s["section_name"] == section_name), None
        )
        if new_section is None:
            return jsonify({"error": f'Section "{section_name}" not found in regenerated report.'}), 404

        # Patch the existing report
        existing["sections"] = [
            new_section if s["section_name"] == section_name else s
            for s in existing.get("sections", [])
        ]
        REPORT_PATH.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # Reset review record to pending (regeneration invalidates prior approval)
        record = load_review_record(REVIEW_RECORD_PATH)
        data_dict = record.to_dict()
        data_dict["review_status"] = "pending"
        data_dict["finalization_blocked"] = True
        data_dict["reviewer"] = None
        data_dict["timestamp"] = None
        data_dict["comments"] = ""
        # Remove section from approved/flagged since it was regenerated
        data_dict["approved_sections"] = [
            s for s in data_dict.get("approved_sections", []) if s != section_name
        ]
        data_dict["flagged_sections"] = [
            s for s in data_dict.get("flagged_sections", []) if s != section_name
        ]
        save_review_record(ReviewRecord(data_dict), REVIEW_RECORD_PATH)

        return jsonify({"message": f'Section "{section_name}" regenerated. Review reset to pending.'})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/status")
def api_status():
    """Return the current review record as JSON."""
    _ensure_review_record()
    record = load_review_record(REVIEW_RECORD_PATH)
    return jsonify(record.to_dict())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("GenAR PADER Review UI — http://localhost:5000")
    print(f"Report:        {REPORT_PATH}")
    print(f"Review record: {REVIEW_RECORD_PATH}")
    app.run(debug=False, port=5000)


if __name__ == "__main__":
    main()
