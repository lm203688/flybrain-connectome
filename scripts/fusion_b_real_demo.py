"""
Fusion B real-world demo — TwoStageLLMBackend on actual P1-style tasks.

Uses the local LLM gateway (127.0.0.1:8788) with two real models:
  * cheap: sensenova-6.8-flash-lite (lightweight, fast)
  * strong: deepseek-v4-flash (high-performance)

Measures: cost savings, latency, semantic agreement.

Key finding (2026-10-11):
  * 100% cheap hits, 0% escalation → 5× cost reduction
  * 3-16× faster than strong-only
  * 80% semantic agreement (3/5 diffs are punctuation/case only)
  * Cheap model answered task 1 CORRECTLY while strong model was WRONG
  * Confidence score gives 1.0 to ALL short answers — routing signal, not judgement

Discipline per OPEN_SOURCE_FUSION §4:
  * Confidence is a ROUTING signal, not a JUDGEMENT signal
  * The two-stage backend must NEVER silently downgrade
  * Agreement is measured semantically, not by exact string match
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))

from llm_orchestrator import (  # noqa: E402
    TwoStageLLMBackend,
    HTTPLLMBackend,
    answer_confidence_score,
)


SYSTEM_PROMPT = "You are a graph theory assistant. Answer concisely."

TASKS = [
    {
        "id": "hub_identification",
        "prompt": "Which node is the inhibitory hub in this small feedforward motif? Answer with one word.",
        "expected": "hub",
    },
    {
        "id": "shortest_path",
        "prompt": "What is the shortest path length in a graph with 5 nodes and edges A->B, B->C, C->D, D->A? Answer with a number.",
        "expected": "3",
    },
    {
        "id": "cycle_detection",
        "prompt": "Is there a cycle in this directed graph: A->B, B->C, C->A? Answer yes or no.",
        "expected": "yes",
    },
    {
        "id": "complete_graph_edges",
        "prompt": "How many edges does a complete graph with 4 nodes have? Answer with a number.",
        "expected": "6",
    },
    {
        "id": "clustering_coefficient",
        "prompt": "What is the clustering coefficient range for a triangle graph? Answer low, medium, or high.",
        "expected": "high",
    },
]


def normalize(text: str) -> str:
    """Normalize for semantic comparison (strip punctuation, lowercase)."""
    return text.strip().lower().rstrip(".!?")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8788/v1")
    p.add_argument("--cheap-model", default="sensenova-6.8-flash-lite")
    p.add_argument("--strong-model", default="deepseek-v4-flash")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--check", action="store_true",
                   help="Assert Fusion B premises on real LLM")
    args = p.parse_args()

    strong = HTTPLLMBackend(base_url=args.strong_model.replace("http://", "").replace("https://", ""),
                           model=args.strong_model if args.strong_model.startswith("http") else "deepseek-v4-flash",
                           max_tokens=64, temperature=0.0)
    # Fix: use proper base_url
    strong = HTTPLLMBackend(base_url=args.base_url, model=args.strong_model,
                           max_tokens=64, temperature=0.0)
    cheap = HTTPLLMBackend(base_url=args.base_url, model=args.cheap_model,
                           max_tokens=64, temperature=0.0)

    print("=" * 60)
    print("Fusion B Real-World Demo: TwoStageLLMBackend")
    print("=" * 60)
    print(f"  Cheap model:  {args.cheap_model}")
    print(f"  Strong model: {args.strong_model}")
    print(f"  Base URL:     {args.base_url}")
    print()

    # --- Strong-only baseline ---
    print("--- Strong-only (deepseek-v4-flash) ---")
    strong_results = []
    for task in TASKS:
        t0 = time.time()
        try:
            ans = strong.chat(SYSTEM_PROMPT, task["prompt"])
            dt = time.time() - t0
            status = "OK"
        except Exception as e:
            ans = f"ERROR: {e}"
            dt = time.time() - t0
            status = "FAIL"
        norm = normalize(ans)
        correct = norm == task["expected"].lower()
        strong_results.append({
            "id": task["id"], "answer": ans, "time_s": round(dt, 1),
            "correct": correct, "status": status,
        })
        print(f"  {task['id']:25s}: {ans[:40]!r:40s} ({dt:5.1f}s) {'✓' if correct else '✗'}")

    # --- Two-stage pipeline ---
    print()
    print("--- Two-stage (cheap→strong) ---")
    two_stage = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    ts_results = []
    for task in TASKS:
        t0 = time.time()
        try:
            ans = two_stage.chat(SYSTEM_PROMPT, task["prompt"])
            dt = time.time() - t0
            status = "OK"
        except Exception as e:
            ans = f"ERROR: {e}"
            dt = time.time() - t0
            status = "FAIL"
        conf = answer_confidence_score(ans)
        norm = normalize(ans)
        correct = norm == task["expected"].lower()
        ts_results.append({
            "id": task["id"], "answer": ans, "time_s": round(dt, 1),
            "confidence": round(conf, 2), "correct": correct, "status": status,
        })
        print(f"  {task['id']:25s}: {ans[:40]!r:40s} ({dt:5.1f}s, conf={conf:.1f}) {'✓' if correct else '✗'}")

    # --- Metrics ---
    print()
    print("=" * 60)
    print("METRICS")
    print("=" * 60)

    # Cost
    cheap_calls = two_stage.stats["cheap_calls"]
    strong_calls = two_stage.stats["strong_calls"]
    total_calls = two_stage.stats["total_calls"]
    strong_only_cost = len(TASKS) * 5  # 5x ratio
    two_stage_cost = cheap_calls + strong_calls * 5
    cost_saving = (1 - two_stage_cost / strong_only_cost) * 100

    print(f"  Total calls:    {total_calls}")
    print(f"  Cheap calls:    {cheap_calls}")
    print(f"  Strong calls:   {strong_calls}")
    print(f"  Escalations:    {two_stage.stats['escalations']}")
    print(f"  Cheap hit rate: {two_stage.cheap_hit_rate:.0%}")
    print(f"  Escalation rate:{two_stage.escalation_rate:.0%}")
    print(f"  Cost (strong=5): strong-only={strong_only_cost}, two-stage={two_stage_cost}")
    print(f"  Cost savings:   {cost_saving:.1f}%")

    # Speed
    strong_avg_time = sum(r["time_s"] for r in strong_results) / len(strong_results)
    ts_avg_time = sum(r["time_s"] for r in ts_results) / len(ts_results)
    speedup = strong_avg_time / ts_avg_time if ts_avg_time > 0 else 0
    print(f"  Avg time (strong): {strong_avg_time:.1f}s")
    print(f"  Avg time (two-stage): {ts_avg_time:.1f}s")
    print(f"  Speedup: {speedup:.1f}×")

    # Agreement
    print()
    print("  Agreement (semantic):")
    exact = 0
    semantic = 0
    for sr, tr in zip(strong_results, ts_results):
        s_norm = normalize(sr["answer"])
        t_norm = normalize(tr["answer"])
        if s_norm == t_norm:
            exact += 1
            semantic += 1
        else:
            print(f"    DIFF: {sr['id']}")
            print(f"      strong: {sr['answer']!r}")
            print(f"      two-stage: {tr['answer']!r}")
    print(f"  Exact match: {exact}/{len(TASKS)} = {exact/len(TASKS):.0%}")

    # Accuracy
    strong_correct = sum(1 for r in strong_results if r["correct"])
    ts_correct = sum(1 for r in ts_results if r["correct"])
    print(f"  Strong-only accuracy: {strong_correct}/{len(TASKS)} = {strong_correct/len(TASKS):.0%}")
    print(f"  Two-stage accuracy:   {ts_correct}/{len(TASKS)} = {ts_correct/len(TASKS):.0%}")

    # --- Check ---
    if args.check:
        # Fusion B premises on real LLM:
        # 1. At least 50% cost savings (vs strong-only)
        # 2. At least 60% semantic agreement (exact + punctuation-normalized)
        semantic_pct = exact / len(TASKS) * 100
        ok = cost_saving >= 50.0 and semantic_pct >= 60.0
        print()
        if ok:
            print(f"  FUSION B REAL CHECK PASS — {cost_saving:.1f}% cost savings, "
                  f"{semantic_pct:.0f}% exact agreement")
            return 0
        else:
            print(f"  FUSION B REAL CHECK FAIL — savings={cost_saving:.1f}% "
                  f"(need ≥50%), agreement={semantic_pct:.0f}% (need ≥60%)")
            return 1

    # Save output
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        output = {
            "strong_model": args.strong_model,
            "cheap_model": args.cheap_model,
            "n_tasks": len(TASKS),
            "strong_results": strong_results,
            "two_stage_results": ts_results,
            "stats": two_stage.stats,
            "cost_saving_pct": round(cost_saving, 1),
            "speedup": round(speedup, 1),
            "strong_accuracy": strong_correct / len(TASKS),
            "two_stage_accuracy": ts_correct / len(TASKS),
            "exact_agreement": exact / len(TASKS),
            "key_finding": (
                "Confidence score gives 1.0 to ALL short clean answers, "
                "including wrong ones. The confidence score is a ROUTING "
                "signal (short + no hedge = confident), not a JUDGEMENT "
                "signal (is the answer correct?). This is the '判据模型不是权威' "
                "principle from Fusion A applied to Fusion B."
            ),
        }
        out_path = out / "fusion_b_real_demo.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"\n  Output: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
