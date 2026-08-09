"""
evaluation/benchmark.py

Multi-provider benchmarking harness for ClearScan.

Runs the same set of real radiology reports (backend/data/radiology_dataset.csv)
through every configured LLM provider (groq / gemini / openai / ollama) and
measures four things per provider:

  1. Accuracy       - % of the dataset's known medical terms that show up in
                       the AI-generated summary (term recall), plus how often
                       the app's risk_level matches the dataset's severity label.
  2. Latency        - wall-clock time per generate_explanation() call.
  3. Cost           - estimated $ cost per call, based on token counts and a
                       small pricing table (see PRICING below - these are
                       ballpark public rates and should be checked/updated).
  4. Reliability    - % of calls that returned a real answer instead of an
                       error / fallback message (e.g. "Ollama is not running").

Usage
-----
    cd backend
    python ../evaluation/benchmark.py
    python ../evaluation/benchmark.py --providers groq gemini --limit 10
    python ../evaluation/benchmark.py --providers ollama --ollama-model llama3.2:1b --all

Output
------
    evaluation/benchmark_results.csv   - one row per (report, provider) call
    evaluation/benchmark_summary.csv   - aggregated stats per provider
    A summary table is also printed to the console.

Notes
-----
- This calls the SAME generate_explanation() pipeline the Flask app uses
  (retrieval + prompt building + the real provider call), so results reflect
  the whole system, not just the raw LLM.
- Requires valid API keys in backend/.env for whichever providers you test,
  and (for ollama) a local `ollama serve` running.
- Token counts are ESTIMATES (tiktoken if installed, else a word-count
  heuristic) because the provider service modules currently only return the
  response text, not usage stats. Good enough for relative cost comparison;
  not exact billing.
"""

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from statistics import mean

# ── Make backend/ importable, same way app.py expects to be run ──────────────
BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from services.rag_service import generate_explanation  # noqa: E402

DATASET_PATH = os.path.join(BACKEND_DIR, "data", "radiology_dataset.csv")
RESULTS_CSV  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.csv")
SUMMARY_CSV  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_summary.csv")

ALL_PROVIDERS = ["groq", "gemini", "openai", "ollama"]

# Strings the app returns when a provider fails / falls back - used to detect
# a "failed" call even though generate_with_provider() didn't raise.
FAILURE_MARKERS = [
    "AI Service Temporary Issue",
    "is not responding right now",
    "Ollama is not running",
    "did not return a response",
]

# ── Approximate public pricing, USD per 1M tokens ($/1M in, $/1M out) ────────
# These are ballpark figures and change over time - update before quoting
# them in a report. "openai" here actually routes through OpenRouter's free
# tier model (see backend/services/openai_service.py), so it's $0.
PRICING = {
    "groq":   (0.59, 0.79),   # llama-3.3-70b-versatile on Groq
    "gemini": (0.10, 0.40),   # gemini-2.5-flash-lite via OpenRouter (2.0 was shut down 1 Jun 2026)
    "openai": (0.0, 0.0),     # openrouter/free model
    "ollama": (0.0, 0.0),     # local - no per-token cost
}

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text):
        return len(_ENC.encode(text or ""))
except ImportError:
    def count_tokens(text):
        # Rough heuristic: ~1.3 tokens per word for English text.
        words = (text or "").split()
        return int(len(words) * 1.3)


def load_dataset(limit=None):
    with open(DATASET_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if limit:
        rows = rows[:limit]
    return rows


def expected_terms(medical_terms_field):
    """'cardiomegaly: enlargement...; pleural effusion: fluid...' -> ['cardiomegaly', 'pleural effusion']"""
    terms = []
    for chunk in (medical_terms_field or "").split(";"):
        name = chunk.split(":")[0].strip().lower()
        if name:
            terms.append(name)
    return terms


def expected_risk_level(dataset_severity):
    """Map the dataset's 5-value severity scale onto the app's 3-value risk_level scale."""
    mapping = {
        "critical": "High",
        "high":     "High",
        "moderate": "Medium",
        "low":      "Low",
        "normal":   "Low",
    }
    return mapping.get((dataset_severity or "").strip().lower(), "Medium")


def estimate_cost(provider, prompt_text, completion_text):
    in_rate, out_rate = PRICING.get(provider, (0.0, 0.0))
    in_tokens  = count_tokens(prompt_text)
    out_tokens = count_tokens(completion_text)
    cost = (in_tokens / 1_000_000) * in_rate + (out_tokens / 1_000_000) * out_rate
    return in_tokens, out_tokens, cost


def is_failure(summary_text):
    return any(marker.lower() in (summary_text or "").lower() for marker in FAILURE_MARKERS)


def run_benchmark(providers, limit, all_rows, ollama_model):
    rows = load_dataset(limit=None if all_rows else (limit or 10))
    results = []

    total_calls = len(rows) * len(providers)
    call_num = 0

    for provider in providers:
        for row in rows:
            call_num += 1
            report_text = row["findings"]
            terms_wanted = expected_terms(row["medical_terms"])
            severity_wanted = expected_risk_level(row["severity"])

            print(f"[{call_num}/{total_calls}] {provider:8s} | id={row['id']:>3s} | {row['report_type']}")

            start = time.perf_counter()
            try:
                result = generate_explanation(
                    report_text,
                    provider=provider,
                    ollama_model=ollama_model,
                    allow_fallback=False,  # isolate this provider - don't let a
                                           # failure secretly get answered by
                                           # another provider under this label
                )
                elapsed = time.perf_counter() - start
                summary = result.get("summary", "")
                risk_level = result.get("risk_level", "")
                failed = is_failure(summary)
            except Exception as e:
                elapsed = time.perf_counter() - start
                summary = f"EXCEPTION: {e}"
                risk_level = ""
                failed = True

            summary_lower = summary.lower()
            terms_found = [t for t in terms_wanted if t in summary_lower]
            term_recall = (len(terms_found) / len(terms_wanted)) if terms_wanted else None

            severity_match = (risk_level == severity_wanted) if risk_level else None

            in_tok, out_tok, cost = estimate_cost(provider, report_text, summary)

            results.append({
                "id": row["id"],
                "provider": provider,
                "report_type": row["report_type"],
                "latency_sec": round(elapsed, 3),
                "success": not failed,
                "term_recall": round(term_recall, 3) if term_recall is not None else "",
                "expected_severity": severity_wanted,
                "actual_risk_level": risk_level,
                "severity_match": severity_match if severity_match is not None else "",
                "est_prompt_tokens": in_tok,
                "est_completion_tokens": out_tok,
                "est_cost_usd": round(cost, 6),
            })

    return results


def write_results_csv(results, path):
    if not results:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)


def summarize(results):
    by_provider = defaultdict(list)
    for r in results:
        by_provider[r["provider"]].append(r)

    summary_rows = []
    for provider, rows in by_provider.items():
        n = len(rows)
        successes = [r for r in rows if r["success"]]
        recalls = [r["term_recall"] for r in rows if r["term_recall"] != ""]
        matches = [r["severity_match"] for r in rows if r["severity_match"] != ""]

        summary_rows.append({
            "provider": provider,
            "calls": n,
            "reliability_pct": round(100 * len(successes) / n, 1) if n else 0,
            "avg_term_recall_pct": round(100 * mean(recalls), 1) if recalls else 0,
            "severity_match_pct": round(100 * (sum(1 for m in matches if m) / len(matches)), 1) if matches else 0,
            "avg_latency_sec": round(mean(r["latency_sec"] for r in rows), 2) if rows else 0,
            "total_est_cost_usd": round(sum(r["est_cost_usd"] for r in rows), 4),
        })

    return summary_rows


def print_summary_table(summary_rows):
    headers = ["provider", "calls", "reliability_pct", "avg_term_recall_pct",
               "severity_match_pct", "avg_latency_sec", "total_est_cost_usd"]
    col_w = {h: max(len(h), max((len(str(r[h])) for r in summary_rows), default=0)) for h in headers}

    def fmt_row(vals):
        return " | ".join(str(v).ljust(col_w[h]) for h, v in zip(headers, vals))

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print(fmt_row(headers))
    print("-" * 70)
    for r in summary_rows:
        print(fmt_row([r[h] for h in headers]))
    print("=" * 70)
    print(f"Full per-call results: {RESULTS_CSV}")
    print(f"Summary table:         {SUMMARY_CSV}\n")


def main():
    parser = argparse.ArgumentParser(description="Benchmark ClearScan's LLM providers.")
    parser.add_argument("--providers", nargs="+", choices=ALL_PROVIDERS, default=ALL_PROVIDERS,
                         help="Which providers to test (default: all four).")
    parser.add_argument("--limit", type=int, default=10,
                         help="Number of dataset reports to test per provider (default: 10).")
    parser.add_argument("--all", action="store_true",
                         help="Use the entire 50-report dataset instead of --limit.")
    parser.add_argument("--ollama-model", default="llama3.2:1b",
                         help="Ollama model to use if 'ollama' is in --providers.")
    args = parser.parse_args()

    print(f"Testing providers: {args.providers}")
    print(f"Dataset: {'all 50 rows' if args.all else f'{args.limit} rows'}\n")

    results = run_benchmark(args.providers, args.limit, args.all, args.ollama_model)

    write_results_csv(results, RESULTS_CSV)
    summary_rows = summarize(results)
    write_results_csv(summary_rows, SUMMARY_CSV)
    print_summary_table(summary_rows)


if __name__ == "__main__":
    main()