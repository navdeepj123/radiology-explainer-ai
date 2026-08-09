# Evaluation Metrics

## Purpose

ClearScan can generate patient explanations using four different LLM providers
(Groq, Gemini, OpenAI, Ollama). This document defines how we measure and
compare them, using `evaluation/benchmark.py` and the labeled dataset in
`backend/data/radiology_dataset.csv` (50 real-style radiology reports across
19 report types, each with known medical terms and a severity label).

## Metrics

| Metric | Definition | How it's computed |
|---|---|---|
| **Accuracy - term recall** | % of the report's known medical terms that appear in the AI-generated summary | For each dataset row, we take the ground-truth term list (`medical_terms` column) and check how many appear (case-insensitive substring match) in the returned HTML summary |
| **Accuracy - severity match** | Whether the app's `risk_level` (Low/Medium/High) agrees with the dataset's ground-truth `severity` | Dataset severities (Critical/High/Moderate/Low/Normal) are mapped onto the app's 3-level scale (Critical→High, High→High, Moderate→Medium, Low→Low, Normal→Low), then compared to the `risk_level` returned by `generate_explanation()` |
| **Latency** | Wall-clock seconds for one `generate_explanation()` call | `time.perf_counter()` around the call |
| **Cost** | Estimated USD cost per call | `(estimated prompt tokens / 1M) * input rate + (estimated completion tokens / 1M) * output rate`, using the pricing table in `benchmark.py`. Token counts use `tiktoken` if installed, otherwise a word-count heuristic. These are estimates for relative comparison, not exact billing. |
| **Reliability** | % of calls that returned a real answer rather than an error/fallback message | We check the returned summary text against known failure strings (e.g. "Ollama is not running", "AI Service Temporary Issue") |

## Why term recall + severity match, not just "looks good"

Grading an AI-generated explanation as "good" or "bad" by reading it is
subjective and doesn't scale across 4 providers x 50 reports. Term recall and
severity match are both derived from the dataset's ground truth, so they give
a repeatable, numeric score instead of a gut feeling - this is what lets us
say "Provider X caught more of the actual findings than Provider Y" with
evidence instead of an opinion.

## Known limitations

- Term recall is a **substring** match, so it under-counts a provider that
  correctly explains a finding using different wording (e.g. "enlarged heart"
  instead of "cardiomegaly"), or when the ground-truth term is a different
  grammatical form of what's in the report (e.g. dataset lists "mediastinum"
  as a separate term when the report only says "mediastinal shift"). It's a
  reasonable proxy but not perfect - a natural next step is embedding-based
  similarity instead of exact substring matching (see the semantic-RAG
  proposal in `docs/proposal.md`).
- Cost figures are estimates based on published rates at the time this was
  written and approximate token counts - re-check current pricing before
  quoting exact dollar figures in a report.
- The dataset is synthetic/curated for this project, not real hospital data,
  so results describe relative provider performance on this task, not
  clinical accuracy in general.

## Fix: negated findings were inflating "missed term" counts

Early runs showed suspiciously low term recall (~54%) that was identical
across providers on the same report - a sign the problem wasn't the LLMs.
Investigating individual low-scoring rows (e.g. a Brain CT report reading
"No acute intracranial hemorrhage. No mass effect... Mild cortical atrophy.")
showed the dataset's `medical_terms` column lists every term mentioned in the
findings text, including ones the radiologist explicitly **ruled out** with
"No X". The app deliberately never claims a negated finding as "confirmed"
(see `is_negated()` in `backend/services/retriever.py` - this exists to stop
the AI telling a patient they have a finding the report says they don't have),
so it was being marked "wrong" for correctly staying silent on ruled-out
findings.

`benchmark.py`'s `expected_terms()` now reuses the same `is_negated()` check
to exclude negated terms from the expected set before scoring recall, so the
metric measures what it's supposed to: did the AI catch the *real* positive
findings, not "did it also hallucinate the ruled-out ones."

## How to run

```bash
cd backend
python ../evaluation/benchmark.py --providers groq gemini --limit 10
python ../evaluation/benchmark.py --all          # full 50-report dataset, all providers
```

Outputs `evaluation/benchmark_results.csv` (per-call detail) and
`evaluation/benchmark_summary.csv` (aggregated per provider), plus a summary
table printed to the console.