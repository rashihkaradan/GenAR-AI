# GenAR — AI-Powered PADER Report Generation System

> **TECHNICAL EVALUATION EXERCISE — NOT A REAL REGULATORY SUBMISSION.**  
> This project was built for the GenAR AI Engineering Challenge. It demonstrates safe, evidence-grounded pharmacovigilance AI and must not be submitted to any regulatory authority.

---

## Project Overview

GenAR generates PADER-style (Periodic Adverse Drug Experience Report) safety reports from raw FAERS ICSR data using a hybrid architecture: **deterministic Pandas analysis** for all numerical facts, and a **language model** for narrative prose generation only.

The system enforces a strict evidence boundary — the LLM never sees raw patient data, never performs calculations, and cannot introduce an unsupported number without the automated validator catching it. A mandatory human review step must be completed before any report is finalized.

**Substance:** Bisoprolol  
**Dataset:** OpenFDA FAERS (1 024 unique cases, reporting period 2024-12-27 – 2025-12-26)  
**Output:** Structured JSON report + 22-page professional PDF

---

## Problem Statement

Producing a PADER report manually from FAERS data requires:
1. Ingesting and cleaning large ICSR datasets
2. Computing case counts, reaction frequencies, and demographic distributions
3. Writing regulatory prose that is accurate, hedged, and section-structured
4. Validating that all numbers in the prose match the source data
5. Obtaining human expert review before submission

This process is time-consuming, error-prone, and difficult to audit. GenAR automates steps 1–4 while keeping a human in the loop for step 5.

---

## Architecture

```
CSV → Validation → Normalization → Deterministic Analysis → Evidence Store
    → Context Builder → LLM → Report Generation → Validation
    → Human Review → Final PDF
```

Full component diagram: [docs/architecture.md](docs/architecture.md)

---

## Data Flow

1. **CSV** — Raw FAERS ICSR file (`data/*.csv`) is read-only; never modified.
2. **Validation** — Row-level checks (null ID, invalid date, empty PT). Warnings for unexpected categoricals.
3. **Normalization** — Deterministic field standardisation (casefold, age-unit conversion, age-group binning, outcome token normalization). Raw columns preserved with `raw_` prefix.
4. **Deterministic Analysis** — Pandas computes all metrics: case counts, reaction frequencies, demographics, outcomes, alerts, trends. Written to `data/analysis_results.json`.
5. **Evidence Store** — Named evidence items (`EV-CASE-001`, `EV-REACT-001`, …) built from analysis. SHA-256 of analysis JSON recorded for integrity. Written to `data/evidence.json`.
6. **Context Builder** — Builds minimal, section-specific evidence packets (no raw data). Verifies analysis SHA-256.
7. **LLM** — Writes regulatory prose for each section using only the evidence packet. Returns `{section, content, evidence_ids}`.
8. **Report Generation** — Orchestrates LLM calls, generates structured case index deterministically, writes `output/pader_report.json`.
9. **Automated Validation** — Extracts all literal numbers from prose; verifies each appears in cited evidence. PASS/FAIL gate.
10. **Human Review** — Flask UI at `http://localhost:5000`. Reviewer approves/flags/rejects. Validation must be PASS before approval is allowed.
11. **Finalization** — `finalize.py` writes `output/pader_report_FINAL.json` (requires both gates).
12. **PDF** — ReportLab generates 22-page `output/Bisoprolol_PADER_Report.pdf` with 7 deterministic charts.

---

## Why Python/Pandas for Deterministic Analysis

Regulatory pharmacovigilance requires defensible, reproducible numerical results. Pandas `nunique`, `value_counts`, and `groupby` operations are:
- **Deterministic:** Same input → same output, every time
- **Auditable:** Every formula is explicit, version-controlled code
- **Testable:** Covered by unit tests asserting exact values
- **Fast:** Milliseconds on 1 024-row datasets

An LLM cannot be used for counting — it is probabilistic, opaque, and cannot be unit-tested for exact numerical outputs. See [docs/design_decisions.md](docs/design_decisions.md) for full rationale.

---

## Why LLM for Narrative Generation

PADER reports require regulatory prose that contextualises statistics, acknowledges limitations, and uses appropriate clinical hedging language. This is where language models excel. The LLM is constrained to work only within a pre-approved evidence envelope — it cannot introduce unsupported numbers. A post-generation validator enforces this boundary.

---

## Context Engineering Approach

Each report section receives a minimal, pre-validated **evidence packet** — a JSON object containing only the approved aggregate values for that section. Raw patient records are never in any prompt. The `ContextBuilder` enforces a section → evidence ID whitelist and verifies SHA-256 integrity before building packets. See [docs/design_decisions.md § 3](docs/design_decisions.md).

---

## Evidence / Traceability Approach

Every fact in the PDF maps to a named evidence item:

```
PDF text → evidence_id → evidence.json → analysis_results.json → source CSV
```

Evidence IDs use namespaced prefixes: `EV-PERIOD-`, `EV-CASE-`, `EV-REACT-`, `EV-DEMO-`, `EV-OUTCOME-`, `EV-ALERT-`, `EV-TREND-`, `EV-LIMIT-`. See [docs/design_decisions.md § 4](docs/design_decisions.md).

---

## Human Review Process

A mandatory human review gate sits between automated generation and finalization:

- Validation status must be **PASS** before approval is possible
- Reviewer sees all 7 required panels (dataset status, analysis, sections, evidence, validation, warnings)
- Per-section actions: Approve, Flag, Regenerate
- Whole-report actions: Approve, Flag for Review, Reject Finalization
- Review record is written to `output/review_record.json`
- `finalize.py` checks both gates before writing the FINAL report

---

## Validation Approach

Two independent layers:

1. **Dataset Validation** (`src/ingestion/validator.py`) — Row-level checks before analysis. Errors invalidate rows; warnings are logged.
2. **Report Validation** (`src/validation/report_validator.py`) — Post-generation numeric gate. Extracts every literal number, date, and month from prose; verifies each against cited evidence. Any unsupported number → FAIL → blocks finalization.

---

## Prompt Design

Templates in `prompts/*.txt` use a `{{evidence_packet}}` placeholder. The system prompt instructs the model to:
- Use only numbers from the evidence packet
- Not infer clinical conclusions or assess expectedness
- Cite evidence IDs in the response

OpenAI structured JSON output (`json_schema` mode) is enforced, requiring `section`, `content`, and `evidence_ids` fields. See [docs/design_decisions.md § 6](docs/design_decisions.md).

---

## Model Used

- **Default model:** `gpt-5` (OpenAI Responses API)
- **Configurable via:** `OPENAI_MODEL` environment variable
- **Client abstraction:** `src/ai/model_client.py` — swap providers by implementing `ModelClient`
- **Test stub:** `StaticModelClient` (no API calls, no key required)

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes (for LLM generation only) | OpenAI API key |
| `OPENAI_MODEL` | No | Model name (default: `gpt-5`) |

> **Security:** API keys are read from environment variables only. They are never hardcoded, never logged, and never written to any output file. `.env` files should be in `.gitignore`.

---

## Installation

```powershell
# Clone / open the project
cd you-are-working-on-the-genar

# Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Dependencies:** `pandas`, `openpyxl`, `openai`, `flask`, `reportlab`, `pytest`

---

## How to Run the Project

### Step 1 — Ingest and validate the dataset
```powershell
python -m src.ingestion.ingest_csv
```
Outputs: `data/normalized_cases.jsonl`, `data/validation_report.json`

### Step 2 — Run deterministic analysis
```powershell
python -m src.analysis.analysis_runner
```
Output: `data/analysis_results.json`

### Step 3 — Build evidence store
```powershell
python -m src.evidence.evidence_builder
```
Output: `data/evidence.json`

### Step 4 — Generate the PADER report  
*(Requires `OPENAI_API_KEY`; falls back to template text offline)*
```powershell
$env:OPENAI_API_KEY = "sk-..."
python -m src.reporting.report_generator
```
Output: `output/pader_report.json`, `output/review_record.json`

### Step 5 — Validate the report
```powershell
python -m src.validation.report_validator
```
Output: `output/validation_report.json`

### Step 6 — Human review
```powershell
python -m src.review.review_ui
# Open http://localhost:5000 in a browser
# Review all sections, then Approve
```

### Step 7 — Finalize
```powershell
python -m src.review.finalize
```
Output: `output/pader_report_FINAL.json`

### Step 8 — Generate PDF
```powershell
python -m src.report.pdf_generator
```
Output: `output/Bisoprolol_PADER_Report.pdf`

---

## How to Generate a Report (All Steps)

```powershell
# Full pipeline (steps 1-8, assumes API key set)
python -m src.ingestion.ingest_csv
python -m src.analysis.analysis_runner
python -m src.evidence.evidence_builder
python -m src.reporting.report_generator
python -m src.validation.report_validator
# Review at http://localhost:5000 (run review_ui in a separate terminal)
python -m src.review.finalize
python -m src.report.pdf_generator
```

---

## How to Run Tests

```powershell
# All tests (87 tests, ~3 seconds)
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_comprehensive.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## Example Output

### Analysis Values (from `data/analysis_results.json`)

| Metric | Value |
|---|---|
| Total unique cases | 1 024 |
| Serious cases | 1 023 (99.9%) |
| Non-serious cases | 1 |
| Total reaction instances | 3 648 |
| Alert cases (expedited) | 1 023 |
| Fatal outcome (alert cases) | 68 |
| Top PT | Acute kidney injury (n=81) |
| Dominant age group | 65+ years (n=673) |
| Dominant sex | Female (n=503) |
| Reporting period | 2024-12-27 – 2025-12-26 |

### Validation Result

```
Status: PASS
Numeric/date claims checked: 288
Claims failed: 0
```

### PDF Report

- **Location:** `output/Bisoprolol_PADER_Report.pdf`
- **Pages:** 22
- **Sections:** Cover, TOC, 9 report sections, Evidence Appendix
- **Charts:** 7 deterministic charts (seriousness, reactions, age, sex, country, outcome, monthly trend)

---

## Project Structure

```
you-are-working-on-the-genar/
├── data/
│   ├── *.csv                        # Source FAERS dataset (read-only)
│   ├── normalized_cases.jsonl       # Normalized rows (generated)
│   ├── analysis_results.json        # Deterministic analysis (generated)
│   ├── evidence.json                # Named evidence items (generated)
│   └── validation_report.json       # Dataset validation (generated)
├── output/
│   ├── pader_report.json            # Generated report
│   ├── validation_report.json       # Report validation results
│   ├── review_record.json           # Human review state
│   ├── pader_report_FINAL.json      # Finalized report
│   └── Bisoprolol_PADER_Report.pdf  # 22-page PDF
├── prompts/
│   ├── narrative_summary.txt
│   ├── case_analysis.txt
│   ├── reaction_analysis.txt
│   ├── alert_analysis.txt
│   ├── trends.txt
│   └── limitations.txt
├── src/
│   ├── ingestion/                   # CSV load, validate, normalize
│   ├── analysis/                    # Deterministic Pandas analysis
│   ├── evidence/                    # Evidence builder and store
│   ├── ai/                          # Context builder, prompts, model client
│   ├── reporting/                   # Report generator (LLM orchestration)
│   ├── validation/                  # Claim extractor, numeric validator
│   ├── review/                      # Flask UI, review store, finalize CLI
│   └── report/                      # ReportLab PDF (styles, charts, tables)
├── tests/
│   ├── test_validation.py           # Ingestion / normalization tests
│   ├── test_analysis.py             # Analysis metric tests
│   ├── test_evidence.py             # Evidence generation tests
│   ├── test_ai_context.py           # Context builder tests
│   ├── test_report_generator.py     # Report generation tests
│   ├── test_report_validation.py    # Numeric gate tests
│   ├── test_review.py               # Human review gate tests (25 tests)
│   └── test_comprehensive.py        # Full coverage test suite (39 tests)
├── docs/
│   ├── architecture.md              # System architecture and component diagram
│   ├── design_decisions.md          # Technical design rationale
│   └── evaluation.md                # Test results, known limitations, V1 plan
├── DATA_DICTIONARY.md               # Source field descriptions
├── requirements.txt
└── README.md
```

---

## Known Limitations

See [docs/evaluation.md § Known Limitations](docs/evaluation.md) for the full list. Key items:

1. No SOC analysis (no SOC field in source data)
2. Expectedness not assessed (no CCDS supplied)
3. Review UI has no authentication (V0 scope decision)
4. Country field mixed ISO codes and names
5. 87 cases (8.5%) have missing/non-standard age data

---

## Version 1 Improvement Plan

See [docs/evaluation.md § Version 1 Improvement Plan](docs/evaluation.md) for the full roadmap. Highlights:

- MedDRA SOC grouping
- Expectedness assessment from SmPC/CCDS input
- Reviewer authentication (OAuth 2.0)
- Multi-model support (Anthropic, Gemini, Azure)
- Docker containerisation and CI/CD
- REST API wrapper (FastAPI)
- Statistical trend analysis (Poisson/regression)

---

## Security Notes

- No API keys are committed to source code or output files
- The source CSV is never modified by the pipeline
- Raw patient data is never placed in LLM prompts
- Review UI binds to `127.0.0.1` by default (localhost only)