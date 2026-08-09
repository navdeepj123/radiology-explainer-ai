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
from services.retriever import is_negated  # noqa: E402 - reuse the app's own negation logic

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

# Signs a failure was a rate limit rather than a real problem - worth a
# short wait and a retry rather than giving up immediately.
RATE_LIMIT_MARKERS = ["429", "rate limit", "rate_limit", "too many requests"]

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


def expected_terms(medical_terms_field, report_text=None):
    """'cardiomegaly: enlargement...; pleural effusion: fluid...' -> ['cardiomegaly', 'pleural effusion']

    If report_text is given, terms the report explicitly rules out (e.g.
    "No pulmonary embolism") are EXCLUDED from the expected set. The app
    deliberately never claims a negated finding as "confirmed" (see
    services/retriever.py's is_negated()) - that's a safety feature, not a
    miss - so the benchmark shouldn't penalise it as one.
    """
    terms = []
    for chunk in (medical_terms_field or "").split(";"):
        name = chunk.split(":")[0].strip().lower()
        if not name:
            continue
        if report_text and is_negated(name, report_text.lower()):
            continue
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


def call_with_retry(report_text, provider, ollama_model, max_retries=2):
    """Call generate_explanation, retrying with backoff if the failure looks
    like a rate limit (very plausible when hammering a provider with 50
    back-to-back calls) rather than a real problem with the provider."""
    delay = 5
    for attempt in range(max_retries + 1):
        try:
            result = generate_explanation(
                report_text,
                provider=provider,
                ollama_model=ollama_model,
                allow_fallback=False,
            )
            summary = result.get("summary", "")
            if is_failure(summary) and any(m in summary.lower() for m in RATE_LIMIT_MARKERS) and attempt < max_retries:
                print(f"    rate limited - waiting {delay}s before retry {attempt + 1}/{max_retries}")
                time.sleep(delay)
                delay *= 3
                continue
            return result
        except Exception as e:
            if any(m in str(e).lower() for m in RATE_LIMIT_MARKERS) and attempt < max_retries:
                print(f"    rate limited - waiting {delay}s before retry {attempt + 1}/{max_retries}")
                time.sleep(delay)
                delay *= 3
                continue
            raise
    return result


def run_benchmark(providers, limit, all_rows, ollama_model, live_writer=None, live_file=None, call_delay=0.0):
    rows = load_dataset(limit=None if all_rows else (limit or 10))
    results = []

    total_calls = len(rows) * len(providers)
    call_num = 0
    interrupted = False

    for provider in providers:
        for row in rows:
            call_num += 1
            report_text = row["findings"]
            terms_wanted = expected_terms(row["medical_terms"], report_text)
            severity_wanted = expected_risk_level(row["severity"])

            print(f"[{call_num}/{total_calls}] {provider:8s} | id={row['id']:>3s} | {row['report_type']}")

            start = time.perf_counter()
            try:
                result = call_with_retry(report_text, provider, ollama_model)
                elapsed = time.perf_counter() - start
                summary = result.get("summary", "")
                risk_level = result.get("risk_level", "")
                failed = is_failure(summary)
            except KeyboardInterrupt:
                # Ctrl+C mid-call: stop cleanly and keep whatever we already
                # collected instead of losing it.
                print(f"\nInterrupted during {provider} id={row['id']} - "
                      f"keeping {len(results)} completed result(s).")
                interrupted = True
                break
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

            row_result = {
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
            }
            results.append(row_result)

            # Write to disk immediately so a later hang/crash/Ctrl+C doesn't
            # lose the results we've already collected.
            if live_writer is not None:
                live_writer.writerow(row_result)
                live_file.flush()

            if call_delay:
                time.sleep(call_delay)

        if interrupted:
            break

    return results, (call_num if interrupted else total_calls), total_calls


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
        # Only score accuracy on calls that actually succeeded - a failed
        # call is a reliability problem, not evidence the AI got the
        # content wrong, so it shouldn't drag the accuracy average down.
        recalls = [r["term_recall"] for r in successes if r["term_recall"] != ""]
        matches = [r["severity_match"] for r in successes if r["severity_match"] != ""]

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


RESULT_FIELDS = [
    "id", "provider", "report_type", "latency_sec", "success", "term_recall",
    "expected_severity", "actual_risk_level", "severity_match",
    "est_prompt_tokens", "est_completion_tokens", "est_cost_usd",
]


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
    parser.add_argument("--delay", type=float, default=1.0,
                         help="Seconds to wait between calls, to avoid rate limits on "
                              "fast providers like Groq (default: 1.0). Use 0 to disable.")
    args = parser.parse_args()

    print(f"Testing providers: {args.providers}")
    print(f"Dataset: {'all 50 rows' if args.all else f'{args.limit} rows'}\n")
    print(f"Results are saved to disk after every single call, so if this gets "
          f"interrupted (Ctrl+C, a hung provider, a crash) nothing already "
          f"completed is lost - just re-run with a smaller --providers list "
          f"for whichever provider didn't finish.\n")
    print("IMPORTANT (Windows PowerShell/cmd): don't click inside this "
          "terminal window while it's running - Quick Edit Mode will pause "
          "or interrupt the script without any error message.\n")

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        f.flush()

        results, completed_calls, total_calls = run_benchmark(
            args.providers, args.limit, args.all, args.ollama_model,
            live_writer=writer, live_file=f, call_delay=args.delay
        )

    if not results:
        print("No results collected.")
        return

    if completed_calls < total_calls:
        print(f"\n{'!' * 70}")
        print(f"PARTIAL RUN - only {completed_calls}/{total_calls} calls completed "
              f"before this stopped. The numbers below only reflect what ran.")
        print(f"{'!' * 70}")

    summary_rows = summarize(results)
    write_results_csv(summary_rows, SUMMARY_CSV)
    print_summary_table(summary_rows)


if __name__ == "__main__":
    main()