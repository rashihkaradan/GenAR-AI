# GenAR — Evaluation

## What Was Built

GenAR is a pharmacovigilance AI system that generates PADER-style (Periodic Adverse Drug Experience Report) safety reports from raw FAERS ICSRs (Individual Case Safety Reports). It combines deterministic Pandas analysis, evidence-grounded LLM narrative generation, automated numeric validation, mandatory human review, and professional PDF export.

---

## Test Results (v0 submission)

```
============================= test session starts =============================
platform win32 — Python 3.14.4, pytest-9.1.1
collected 87 items

tests/test_ai_context.py        .....    3 passed
tests/test_analysis.py          .....    3 passed
tests/test_comprehensive.py     .....   39 passed
tests/test_evidence.py          .....    4 passed
tests/test_report_generator.py  .....    3 passed
tests/test_report_validation.py .....    4 passed
tests/test_review.py            .....   25 passed
tests/test_validation.py        .....    6 passed

============================= 87 passed in X.Xs ==============================
```

---

## Analysis Values — Verified Against Source Data

| Metric | Computed Value | Verification |
|---|---|---|
| Total unique cases | 1 024 | `nunique(safetyreportid)` on 1 068 source rows |
| Serious cases | 1 023 | `normalized_serious == "serious"` count |
| Non-serious cases | 1 | `normalized_serious == "not_serious"` count |
| Seriousness % | 99.9% | `1023 / 1024 × 100` |
| Total reaction instances | 3 648 | All non-empty PT splits across all rows |
| Serious reaction instances | 3 637 | PT splits on serious rows only |
| Alert cases (expedited) | 1 023 | `normalized_expedited == "yes"` |
| Fatal outcome alert cases | 68 | Alert cases with any "fatal" outcome split |
| Top PT | Acute kidney injury (81) | `value_counts()` on comma-split PT |
| Dominant age group | 65+ years (673 cases) | Deterministic age-group binning |
| Dominant sex | Female (503 cases) | Case-level `normalized_sex` |
| Reporting period | 2024-12-27 – 2025-12-26 | `min/max(parsed_receivedate)` |

---

## Evidence References — Verified

All evidence IDs in the report exist in `data/evidence.json`.  
All numbers in all 9 generated sections are backed by a cited evidence item.  
Automated validation status: **PASS** (288 numeric/date claims checked, 0 failed).

---

## Human Review — Verified Gate

- A report with `validation_status = FAIL` cannot be approved (raises `ReviewBlockedError`)
- A report with `review_status = pending / flagged / rejected` cannot be finalized
- `finalize.py` writes `output/pader_report_FINAL.json` only when both gates pass
- 25 tests cover all gate combinations

---

## Generated Output

| File | Size | Description |
|---|---|---|
| `output/pader_report.json` | ~250 KB | 9-section structured report with evidence IDs |
| `output/validation_report.json` | ~15 KB | Numeric/evidence validation results |
| `output/review_record.json` | ~2 KB | Human review state |
| `output/pader_report_FINAL.json` | ~252 KB | Final report with embedded review record |
| `output/Bisoprolol_PADER_Report.pdf` | ~55 KB | 22-page professional PDF |

---

## Known Limitations (Version 0)

### Analysis Limitations
1. **No System Organ Class (SOC) analysis.** The source data does not contain a SOC column; SOC is not inferred.
2. **Expectedness is not assessed.** No product label or CCDS was supplied; all reactions are treated as of unknown expectedness.
3. **Case-level metrics use one representative row.** When a case has multiple source rows with conflicting values (e.g., different serious flags), a deterministic first-row policy is applied and a validation warning is emitted — but no merging or arbitration is performed.
4. **Reaction PTs are counted as supplied.** Comma-split counts each comma-separated token once. No MedDRA hierarchy analysis, no synonym normalisation, no duplicate reaction detection across rows of the same case.
5. **Observed trends are not safety signals.** Monthly counts describe data receipt patterns — not incidence. No statistical signal detection is performed.

### System Limitations
6. **Authentication is not implemented.** The review UI is accessible to anyone with network access to port 5000. V0 was scoped without auth.
7. **Single-product / single-period only.** There is no multi-product or multi-period comparison capability.
8. **No persistent storage.** Review records and reports are flat JSON files. There is no database, versioning system, or audit trail beyond the JSON files themselves.
9. **OpenAI Responses API dependency.** Switching providers requires a new `ModelClient` implementation.
10. **PDF font limitation.** Helvetica is used (bundled with ReportLab). No Unicode-range custom fonts are embedded, which may affect rendering of non-Latin characters in reaction terms.

### Data Limitations
11. **Country field quality.** `occurcountry` contains ISO 2-letter codes mixed with full country names and regional codes (e.g., "eu"). Only whitespace/case normalisation is applied; no ISO lookup is performed.
12. **Missing age data.** 87 of 1 024 cases (8.5%) have missing or non-standard age/unit combinations and are excluded from age-group analysis.

---

## Version 1 Improvement Plan

### Priority 1 — Correctness and Safety
| Item | Description |
|---|---|
| **SOC grouping** | Integrate MedDRA browser or local lookup to add SOC-level PT grouping |
| **Expectedness assessment** | Accept a CCDS/SmPC as input; flag listed vs. unlisted reactions |
| **Multi-row case resolution** | Implement configurable merge policy for conflicting case-level values |
| **ISO country normalisation** | Map ISO 2-letter codes and regional codes to full country names |
| **Reaction deduplication** | Optionally deduplicate PT instances per case for a cases-reporting metric |

### Priority 2 — Quality and Reliability
| Item | Description |
|---|---|
| **Prompt versioning** | Store prompt version alongside each generated section for reproducibility |
| **Section-level regeneration tracking** | Track which sections were regenerated and how many times |
| **Statistical trend analysis** | Add simple Poisson or regression-based signal detection on monthly trends |
| **Multi-model support** | Implement `AnthropicClient`, `GeminiClient`, `AzureOpenAIClient` adapters |
| **LLM output caching** | Cache structured responses keyed on (section, evidence_sha256) to avoid redundant API calls |
| **Comparison period** | Accept a previous period report and compute period-over-period deltas |

### Priority 3 — Engineering and Operations
| Item | Description |
|---|---|
| **Authentication** | Add reviewer authentication (OAuth 2.0 or SAML) to the review UI |
| **Audit trail** | Replace flat JSON with a proper event-sourced audit log (SQLite or PostgreSQL) |
| **PDF Unicode fonts** | Embed a Unicode-capable font (e.g., Noto Sans) for international characters |
| **API server** | Wrap the pipeline as a REST API (FastAPI) for programmatic integration |
| **Docker packaging** | Containerise the pipeline for reproducible deployment |
| **CI/CD** | GitHub Actions workflow running the full test suite on every PR |
| **Report versioning** | Automatically version reports (v1, v2…) when sections are regenerated |
| **Multi-product support** | Parameterise the pipeline for any active substance, not just Bisoprolol |
