# GenAR — Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAW DATA LAYER                                  │
│                                                                         │
│   ┌──────────────┐                                                      │
│   │  bisoprolol  │  (OpenFDA FAERS CSV — read-only, never modified)     │
│   │   .csv       │                                                      │
│   └──────┬───────┘                                                      │
└──────────┼──────────────────────────────────────────────────────────────┘
           │  pandas.read_csv()
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      INGESTION & VALIDATION                             │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  src/ingestion/validator.py                                      │  │
│   │  • Row-level checks: non-null case ID, parseable date,          │  │
│   │    non-empty reaction PT                                         │  │
│   │  • Categorical warnings: unexpected sex / seriousness values     │  │
│   │  • No imputation — unexpected values kept verbatim              │  │
│   └─────────────────────────┬────────────────────────────────────────┘  │
│                             │  valid rows (warnings logged)              │
│   ┌─────────────────────────▼────────────────────────────────────────┐  │
│   │  src/ingestion/normalizer.py                                     │  │
│   │  • Deterministic field normalization (case-fold, whitespace)     │  │
│   │  • Age-unit conversion (year/month/week/day → years)            │  │
│   │  • Age-group binning (0-1, 2-11, 12-17, 18-64, 65+)            │  │
│   │  • Outcome token normalization (comma-split preserved)           │  │
│   │  • Reporting month derived from receivedate                      │  │
│   │  • Every source column preserved with raw_ prefix               │  │
│   └─────────────────────────┬────────────────────────────────────────┘  │
│                             │                                            │
│                   data/normalized_cases.jsonl                            │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     DETERMINISTIC ANALYSIS                              │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  src/analysis/analysis_runner.py                                 │  │
│   │                                                                  │  │
│   │  Case-level metrics (one representative row per safetyreportid) │  │
│   │  ┌─────────────────────┐  ┌─────────────────────┐              │  │
│   │  │ Reporting Period    │  │ Demographics         │              │  │
│   │  │ • min/max date      │  │ • age-group dist.   │              │  │
│   │  └─────────────────────┘  │ • sex distribution  │              │  │
│   │  ┌─────────────────────┐  │ • country dist.     │              │  │
│   │  │ Case Summary        │  └─────────────────────┘              │  │
│   │  │ • total unique cases│  ┌─────────────────────┐              │  │
│   │  │ • serious / non-ser │  │ Alerts              │              │  │
│   │  │ • seriousness %     │  │ • expedited cases   │              │  │
│   │  └─────────────────────┘  │ • fatal alerts      │              │  │
│   │                           └─────────────────────┘              │  │
│   │  Reaction-level metrics (all source rows, no deduplication)    │  │
│   │  ┌─────────────────────┐  ┌─────────────────────┐              │  │
│   │  │ Reaction Analysis   │  │ Trends              │              │  │
│   │  │ • PT frequency      │  │ • cases_by_month    │              │  │
│   │  │ • serious PT freq.  │  │ • serious_by_month  │              │  │
│   │  └─────────────────────┘  │ • top_reactions_/mo │              │  │
│   │  ┌─────────────────────┐  └─────────────────────┘              │  │
│   │  │ Outcome Analysis    │                                        │  │
│   │  │ • outcome counts    │                                        │  │
│   │  └─────────────────────┘                                        │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                   data/analysis_results.json                             │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        EVIDENCE STORE                                   │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  src/evidence/evidence_builder.py                                │  │
│   │  • Converts analysis metrics to named, versioned evidence items  │  │
│   │  • Each item: evidence_id, value, calculation, source_fields,   │  │
│   │    analysis_level, case_level_or_reaction_level                  │  │
│   │  • SHA-256 of analysis JSON recorded for integrity validation   │  │
│   │  • Limitations explicitly encoded as EV-LIMIT-001               │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                       data/evidence.json                                 │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       CONTEXT ENGINEERING                               │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  src/ai/context_builder.py                                       │  │
│   │  • Section → approved evidence ID whitelist mapping             │  │
│   │  • Builds minimal, section-specific evidence packets            │  │
│   │  • Verifies evidence SHA-256 matches analysis on disk           │  │
│   │  • Raw patient records are never placed in LLM context          │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│               SectionEvidencePacket (JSON serialised)                   │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       LLM NARRATIVE LAYER                               │
│                                                                         │
│   ┌────────────────────────┐   ┌───────────────────────────────────┐   │
│   │  prompts/*.txt         │   │  src/ai/model_client.py           │   │
│   │  • system prompt       │   │  • Provider-neutral interface     │   │
│   │  • {{evidence_packet}} │──▶│  • OpenAI Responses API (gpt-5)  │   │
│   │    placeholder         │   │  • StaticModelClient (tests)      │   │
│   └────────────────────────┘   │  • API key from env var only      │   │
│                                └─────────────┬─────────────────────┘   │
│                                              │  JSON structured output  │
│   ┌──────────────────────────────────────────▼─────────────────────┐   │
│   │  src/reporting/report_generator.py                              │   │
│   │  • Calls LLM once per narrative section                        │   │
│   │  • Case Index (structured) generated deterministically         │   │
│   │  • History of Actions: explicit "no actions" statement         │   │
│   │  • Initialises review_record.json after every run             │   │
│   └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                    output/pader_report.json                              │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AUTOMATED VALIDATION                               │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  src/validation/report_validator.py                              │  │
│   │  + src/validation/claim_extractor.py                            │  │
│   │  + src/validation/numeric_validator.py                          │  │
│   │                                                                  │  │
│   │  For each section:                                               │  │
│   │  1. Extract all literal numbers, dates, months from prose       │  │
│   │  2. Verify every number appears in cited evidence items         │  │
│   │  3. Flag unsupported expectedness claims                        │  │
│   │  4. Verify every cited evidence ID exists in evidence store     │  │
│   │  Status: PASS (0 failures) or FAIL (blocks finalization)        │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                  output/validation_report.json                           │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        HUMAN REVIEW                                     │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  src/review/review_ui.py  (Flask, http://localhost:5000)         │  │
│   │  src/review/review_store.py                                      │  │
│   │                                                                  │  │
│   │  Reviewer sees:                                                  │  │
│   │  • Dataset validation status / warnings                         │  │
│   │  • Deterministic analysis results                               │  │
│   │  • Generated section text with evidence IDs                     │  │
│   │  • Report validation status (PASS/FAIL)                         │  │
│   │                                                                  │  │
│   │  Actions: Approve | Flag | Reject | Regenerate Section           │  │
│   │                                                                  │  │
│   │  Gate: validation_status must be PASS to allow Approve           │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│           output/review_record.json  (review_status: approved)          │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FINALIZATION & PDF                                 │
│                                                                         │
│   ┌────────────────────────┐   ┌───────────────────────────────────┐   │
│   │  src/review/finalize.py│   │  src/report/pdf_generator.py     │   │
│   │  • Verifies approval   │   │  + styles.py + charts.py         │   │
│   │  • Embeds review record│   │  + tables.py                     │   │
│   │  • Writes FINAL JSON   │──▶│                                   │   │
│   └────────────────────────┘   │  22-page A4 PDF:                  │   │
│                                │  • Cover page                     │   │
│   output/pader_report_         │  • TOC                            │   │
│         _FINAL.json            │  • 9 report sections              │   │
│                                │  • 7 deterministic charts         │   │
│                                │  • Evidence appendix              │   │
│                                └───────────────────────────────────┘   │
│                                              │                          │
│                          output/Bisoprolol_PADER_Report.pdf             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Map

| Module | Path | Role |
|---|---|---|
| Ingestion | `src/ingestion/` | CSV load, validation, normalization |
| Analysis | `src/analysis/` | Deterministic metrics (Pandas) |
| Evidence | `src/evidence/` | Named evidence items, SHA-256 integrity |
| Context | `src/ai/context_builder.py` | Section-specific LLM context packets |
| Prompts | `prompts/*.txt` | Section prompt templates |
| LLM Client | `src/ai/model_client.py` | Provider-neutral model interface |
| Report Gen | `src/reporting/` | Orchestrates LLM calls, writes JSON report |
| Validation | `src/validation/` | Post-generation numeric/evidence gate |
| Review | `src/review/` | Flask UI, review store, finalize CLI |
| PDF | `src/report/` | ReportLab PDF with charts and tables |

## Key Design Invariants

1. **No raw data crosses the evidence boundary.** LLM prompts contain only pre-approved aggregate evidence items, never source rows.
2. **Analysis is always deterministic.** Given the same input CSV, every metric is exactly reproducible — no randomness, no sampling.
3. **LLM is used only for prose.** Numbers, dates, and categorisation are never delegated to the language model.
4. **Validation gates finalization.** A FAIL status from the automated validator physically prevents `finalize.py` from writing the FINAL report.
5. **Human approval is mandatory.** `review_record.json` with `review_status: approved` is required before `finalize.py` runs.
6. **All numbers in prose are evidence-backed.** The claim extractor verifies that every literal number in every section appears in that section's cited evidence.
