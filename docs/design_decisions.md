# GenAR — Design Decisions

## 1. Why Python / Pandas for Deterministic Analysis

**Decision:** All case counts, reaction frequencies, demographics, outcome distributions, trends, and alert metrics are calculated using pure Python and Pandas — not by the language model.

**Rationale:**

| Concern | Python/Pandas | LLM |
|---|---|---|
| Reproducibility | Identical output for identical input | Non-deterministic |
| Auditability | Every formula is explicit in code | Opaque reasoning |
| Regulatory acceptability | Verifiable computation | Cannot be independently verified |
| Numerical precision | Exact integer counts | May round, hallucinate, or paraphrase |
| Speed | Milliseconds on 1 024 rows | Seconds + API cost per section |
| Testability | Standard unit tests | Cannot be unit-tested for exact outputs |

FAERS pharmacovigilance reports require that case counts and reaction frequencies are defensible. Any numerical discrepancy between the report and the source data could indicate a regulatory deficiency. Pandas `nunique`, `value_counts`, and `groupby` operations are transparent, deterministic, and covered by comprehensive unit tests.

---

## 2. Why LLM for Narrative Generation

**Decision:** The language model writes the prose narrative for each report section — it does not perform calculations.

**Rationale:** PADER reports require professional regulatory prose that:
- Contextualises statistics with appropriate clinical hedging language
- Acknowledges limitations and data gaps explicitly
- Uses ICH E2C(R2) aligned phrasing and terminology
- Avoids over-claiming causality, expectedness, or clinical conclusions

This is precisely what large language models do well: fluent, structured, context-aware text generation within a constrained factual envelope. The factual envelope (the evidence packet) is provided by the deterministic pipeline.

**Safeguard:** Every number in the generated prose is post-validated against the evidence. The LLM cannot introduce an unsupported number without the automated validator catching it and blocking finalization.

---

## 3. Context Engineering Approach

**Problem:** Naive prompting — passing raw data directly to the LLM — creates risks:
- Patient data exposure
- Hallucinated statistics not in the dataset
- LLM performing calculations that may be incorrect
- No traceability between report text and source data

**Solution — Minimal Evidence Packets:**

Each report section receives a carefully curated, pre-validated JSON packet containing only:
1. The approved evidence IDs for that section (the allowlist)
2. The evidence item values — aggregated, named, and calculation-described

```json
{
  "section": "narrative_summary",
  "allowed_evidence_ids": ["EV-CASE-001", "EV-REACT-001", "..."],
  "evidence": [
    {
      "evidence_id": "EV-CASE-001",
      "value": 1024,
      "calculation": "nunique(safetyreportid)",
      "source_fields": ["safetyreportid"],
      "case_level_or_reaction_level": "case"
    }
  ]
}
```

**What the LLM never sees:**
- Individual patient records
- Raw source CSV
- Personally identifiable fields
- Case narratives

**Integrity check:** `ContextBuilder.from_paths()` verifies that the SHA-256 of `analysis_results.json` matches the hash recorded in `evidence.json`. If they differ (e.g., analysis was re-run after evidence was built), an error is raised before any LLM call.

---

## 4. Evidence / Traceability Approach

Every fact reported in the PDF maps to a named evidence item:

```
PDF Section Text → evidence_ids[] → evidence.json item → analysis_results.json metric → normalized_cases.jsonl → source CSV
```

**Evidence ID naming convention:**

| Prefix | Category |
|---|---|
| `EV-PERIOD-` | Reporting period dates |
| `EV-CASE-` | Case-level summary metrics |
| `EV-DEMO-` | Demographic distributions |
| `EV-REACT-` | Reaction / PT frequency |
| `EV-OUTCOME-` | Reaction outcome distribution |
| `EV-ALERT-` | 15-day / expedited analysis |
| `EV-TREND-` | Monthly trend data |
| `EV-LIMIT-` | Explicit analysis limitations |

**Traceability fields on each evidence item:**

| Field | Purpose |
|---|---|
| `evidence_id` | Unique stable identifier |
| `value` | The actual calculated value |
| `unit` | Measurement unit (cases, %, reaction_instances) |
| `calculation` | Human-readable formula |
| `source_fields` | Column names from source CSV |
| `analysis_level` | `case` or `reaction` — documents deduplication scope |

---

## 5. Human Review Process

**Decision:** A mandatory human review step exists between automated generation and finalization. No report can be FINAL without explicit human approval.

**Architecture of the gate:**

```
[Automated Validation: PASS] + [Human: review_status=approved]
              ↓
         FINAL report allowed
```

Either condition alone is insufficient. A FAIL validation status physically prevents approval in `review_store.py` (`ReviewBlockedError`). A pending or flagged review status prevents `finalize.py` from running.

**Review interface provides:**
1. Dataset validation status and all warnings
2. Complete deterministic analysis results with source fields
3. Every generated section with its evidence IDs
4. Expandable inline evidence for each citation
5. Report validation status (PASS/FAIL) with specific error details
6. Per-section approve / flag / regenerate actions
7. Whole-report approve / flag / reject with reviewer name and comments

**Review record schema:**
```json
{
  "review_version": "1.0.0",
  "report_id": "<uuid>",
  "validation_status": "PASS",
  "finalization_blocked": false,
  "review_status": "approved",
  "reviewer": "Reviewer Name",
  "timestamp": "2026-08-15T13:00:00+00:00",
  "comments": "...",
  "approved_sections": ["Reporting Period", "..."],
  "flagged_sections": []
}
```

---

## 6. Prompt Design

**Template structure** (`prompts/<section>.txt`):

```
<system instructions>
You are a regulatory medical writer...
Rules:
- Use ONLY the numbers and dates from the evidence packet
- Do not infer clinical conclusions
- Do not assess expectedness
- Cite evidence IDs where appropriate

<user instructions>
Write the <Section Name> section of a PADER report.

Evidence:
{{evidence_packet}}
```

**Structured output schema** (enforced via OpenAI JSON schema mode):

```json
{
  "section": "string",
  "content": "string",
  "evidence_ids": ["string"]
}
```

This forces the model to declare which evidence IDs it used, which the validator then cross-references against the approved allowlist.

**Why one prompt per section:**
- Minimises context window per call (lower token cost)
- Easier to audit and revise individual sections
- Section regeneration is granular (revise one section without full regeneration)

---

## 7. Validation Approach

Two independent validation layers:

### Layer 1: Dataset Validation (`src/ingestion/validator.py`)
- **Purpose:** Data quality gate before analysis
- **Row-level errors:** Null case ID, unparseable date, empty reaction PT
- **Warnings:** Unexpected categorical values (sex, seriousness)
- **Policy:** Unexpected values retained verbatim — never imputed

### Layer 2: Report Validation (`src/validation/report_validator.py`)
- **Purpose:** Verify generated prose against evidence after LLM run
- **Claim extraction:** Regex-based extraction of all literal numbers, dates, and months
- **Numeric gate:** Every extracted number must appear in that section's cited evidence items
- **Evidence gate:** Every cited evidence ID must exist in the evidence store
- **Expectedness gate:** Phrases like "expected" or "unexpected" trigger warnings
- **Status:** PASS (0 errors) or FAIL (blocks human approval of finalization)

**Key fix in v0.1:** The claim extractor `NUMBER_PATTERN` was updated to use `\b\d+\b` (longest-match-first) to prevent matching "102" as a prefix of "1024". Without this fix, numbers like "1024" generated false positives when the first 3-digit alternative matched greedily.

---

## 8. Model Used

| Setting | Value |
|---|---|
| Model | `gpt-5` (default; configurable via `OPENAI_MODEL`) |
| API | OpenAI Responses API (`client.responses.create`) |
| Output mode | JSON schema (strict) |
| Structured output schema | `pader_section` with `section`, `content`, `evidence_ids` |
| Fallback | `StaticModelClient` for offline/test runs |

The model is configurable — any OpenAI-compatible model supporting structured JSON output can be substituted via the `OPENAI_MODEL` environment variable. The `ModelClient` abstract class makes provider substitution straightforward.

---

## 9. Version 0 Limitations and Version 1 Roadmap

See [evaluation.md](evaluation.md) for full details.
