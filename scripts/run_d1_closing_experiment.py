#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D-1 P1 结案实验 —— LLM 编排基底对照
=====================================

背景：
  PR-2 干预试验在 50 拓扑 × 100 单元网格上 3 次 FAIL
  (composite 38.9% → 71.4% → 59.1%, 效应不随 n 增长)。
  论文正文 §4.4 报出 "0/7 图族上本项目拓扑显著优于随机"。
  D-1 是**唯一能真正结案 0/7** 的实验：把 25 蓝图放到
  LLM 编排基底上，与随机对照 4 种拓扑。

方法：
  1. 13 evidence + 12 random 蓝图（5 节点小图，motif 分布对齐）
  2. 每个蓝图 3 种任务（motif_family / hub / reachability），
     每任务 1 样本 → 25 × 3 = 75 个 (blueprint, task) 元组
  3. 4 种拓扑 × 25 蓝图 × 3 任务 = 300 次编排调用
     - sequential: reason + verify = 2 agent calls
     - fan_out:    3 agents + 1 judge = 4 agent calls
     - hierarchical: planner + executor = 2 agent calls
     - router:     router + specialist = 2 agent calls
  4. 主指标：per-topology accuracy，按 origin (evidence/random) 拆分
  5. 判决：任一 topology 上 evidence > random ≥ 10pp 且 p < 0.05
     → 0/7 结论翻转；否则确认 0/7 在 LLM 编排基底上成立

LLM 后端：SenseNova 代理 http://127.0.0.1:8788/v1
  model=deepseek-v4-flash, reasoning_effort=none, temperature=0, seed=42

用法：
  python scripts/run_d1_closing_experiment.py
  python scripts/run_d1_closing_experiment.py --skip-llm          # 只生成蓝图清单
  python scripts/run_d1_closing_experiment.py --max-calls 60      # 小规模快速试跑
  python scripts/run_d1_closing_experiment.py --workers 8         # 提高并发
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any

# --- 路径注入 --------------------------------------------------------
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MCP_DIR = REPO / "flybrain-connectome-mcp"
for p in (str(REPO), str(MCP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from llm_tasks import (  # noqa: E402
    Blueprint,
    build_evidence_blueprint,
    build_random_blueprint,
    generate_tasks,
    score_answer,
)
from llm_orchestrator import (  # noqa: E402
    HTTPLLMBackend,
    get_orchestrator,
)

STATE_DIR = HERE / "d1_closing_experiment"
STATE_DIR.mkdir(exist_ok=True)
RESULT_FILE = STATE_DIR / "results.json"
LOG_FILE = STATE_DIR / "run.log"

# =====================================================================
# 默认配置
# =====================================================================
DEFAULT_BASE_URL = "http://127.0.0.1:8788/v1"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_SEED = 20261026
N_BLUEPRINTS = 25
N_PER_TYPE = 1
N_AGENTS_FAN_OUT = 3
TASK_TYPES = ("motif_family", "hub", "reachability")
TOPOLOGIES = ("sequential", "fan_out", "hierarchical", "router")
SIGNIFICANCE_ALPHA = 0.05
MARGIN_PP = 10  # 需要 ≥10pp 差才翻转 0/7
BLUEPRINT_SPEC = {"n_nodes": 5, "n_edges": 6}


# =====================================================================
# 工具
# =====================================================================
def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def mc_permutation_test(a: list[bool], b: list[bool],
                        n_perm: int = 5000) -> float:
    """MC 双尾置换检验：观察到的准确率差是否落在 H0 下？"""
    if len(a) < 2 or len(b) < 2:
        return 1.0
    obs_diff = abs(statistics.mean(a) - statistics.mean(b))
    merged = list(a) + list(b)
    na = len(a)
    rng = random.Random(20261026)
    extreme = 0
    for _ in range(n_perm):
        rng.shuffle(merged)
        diff = abs(statistics.mean(merged[:na]) - statistics.mean(merged[na:]))
        if diff >= obs_diff - 1e-12:
            extreme += 1
    return extreme / n_perm


# =====================================================================
# 蓝图生成
# =====================================================================
def build_blueprints(rng: random.Random,
                     n_total: int = N_BLUEPRINTS) -> list[Blueprint]:
    """50/50 混合：一半 evidence，一半 random。

    evidence 蓝图从 3 类 motif 里均匀采样；random 蓝图均匀 DAG，
    节点数与 evidence 对齐。
    """
    n_ev = (n_total + 1) // 2
    n_rn = n_total - n_ev
    blueprints = []
    for i in range(n_ev):
        bp = build_evidence_blueprint(rng, dict(BLUEPRINT_SPEC))
        bp = replace(bp, name=f"ev_{i:03d}_{bp.motif_family}")
        blueprints.append(bp)
    for i in range(n_rn):
        bp = build_random_blueprint(rng, dict(BLUEPRINT_SPEC))
        bp = replace(bp, name=f"rnd_{i:03d}")
        blueprints.append(bp)
    return blueprints


# =====================================================================
# 单任务执行
# =====================================================================
def run_single(
    backend: HTTPLLMBackend,
    task_id: str,
    topology: str,
    prompt: str,
    ground_truth: Any,
    task_type: str,
) -> dict[str, Any]:
    """单任务：调用一次编排，返回 {correct, topology, ...}。"""
    try:
        kwargs: dict[str, Any] = {}
        if topology == "fan_out":
            kwargs["n_agents"] = N_AGENTS_FAN_OUT
        orch = get_orchestrator(topology, backend, evidence=None, **kwargs)
        ans = orch.run(prompt)
        ok = score_answer(ans.text, ground_truth, task_type)
        return {
            "task_id": task_id,
            "topology": topology,
            "task_type": task_type,
            "prompt_chars": len(prompt),
            "answer": ans.text[:200],
            "ground_truth": str(ground_truth),
            "correct": bool(ok),
            "latency_ms": ans.latency_ms,
            "agent_calls": ans.agent_calls,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "task_id": task_id,
            "topology": topology,
            "task_type": task_type,
            "prompt_chars": len(prompt),
            "answer": "",
            "ground_truth": str(ground_truth),
            "correct": False,
            "latency_ms": 0,
            "agent_calls": 0,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }


# =====================================================================
# 分析
# =====================================================================
def analyse(results: list[dict], blueprints: list[Blueprint]) -> tuple:
    """per (topology, origin) accuracy + p-value + verdict。"""
    bp_origin_map = {bp.name: bp.origin for bp in blueprints}

    def origin_of(task_id: str) -> str:
        return bp_origin_map.get(task_id.split("|")[0], "?")

    by_topo_origin: dict[tuple, list[bool]] = {}
    for r in results:
        if r.get("error"):
            continue
        origin = origin_of(r["task_id"])
        if origin == "?":
            continue
        by_topo_origin.setdefault(
            (r["topology"], origin), []
        ).append(bool(r["correct"]))

    log(f"{'topology':<14} {'origin':<10} {'n':>4} {'acc':>7} {'95% CI':>18}")
    log("-" * 62)
    table = []
    for topo in TOPOLOGIES:
        for origin in ("evidence", "random"):
            hits = by_topo_origin.get((topo, origin), [])
            n = len(hits)
            if n == 0:
                log(f"{topo:<14} {origin:<10} {0:>4} {'N/A':>7} {'N/A':>18}")
                continue
            acc = sum(hits) / n
            lo, hi = wilson_ci(sum(hits), n)
            log(f"{topo:<14} {origin:<10} {n:>4} {acc:>7.3f} "
                f"[{lo:.3f}, {hi:.3f}]")
            table.append({"topology": topo, "origin": origin, "n": n,
                          "accuracy": round(acc, 4),
                          "ci_low": round(lo, 4),
                          "ci_high": round(hi, 4)})

    log("")
    log(f"{'topology':<14} {'ev':>7} {'rd':>7} {'diff(pp)':>10} "
        f"{'p-value':>9} {'verdict':<18}")
    log("-" * 74)
    verdicts = []
    any_flip = False
    for topo in TOPOLOGIES:
        ev_hits = by_topo_origin.get((topo, "evidence"), [])
        rd_hits = by_topo_origin.get((topo, "random"), [])
        if len(ev_hits) < 3 or len(rd_hits) < 3:
            log(f"{topo:<14} {'N/A':>7} {'N/A':>7} {'N/A':>10} "
                f"{'N/A':>9} {'sample_too_small':<18}")
            continue
        ev_acc = sum(ev_hits) / len(ev_hits)
        rd_acc = sum(rd_hits) / len(rd_hits)
        diff_pp = (ev_acc - rd_acc) * 100
        p_val = mc_permutation_test(ev_hits, rd_hits, n_perm=5000)
        flip = diff_pp >= MARGIN_PP and p_val < SIGNIFICANCE_ALPHA
        verdict = "FLIP" if flip else "0/7_CONFIRMED"
        if flip:
            any_flip = True
        log(f"{topo:<14} {ev_acc:>7.3f} {rd_acc:>7.3f} {diff_pp:>+10.1f} "
            f"{p_val:>9.4f} {verdict:<18}")
        verdicts.append({"topology": topo,
                         "evidence_acc": round(ev_acc, 4),
                         "random_acc": round(rd_acc, 4),
                         "diff_pp": round(diff_pp, 2),
                         "p_value": round(p_val, 4),
                         "verdict": verdict})

    log("")
    overall = "FLIP" if any_flip else "0/7_CONFIRMED"
    log(f"OVERALL VERDICT: {overall}")
    return table, verdicts, overall


# =====================================================================
# 主入口
# =====================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="D-1 P1 结案实验 · LLM 编排对照")
    ap.add_argument("--n-blueprints", type=int, default=N_BLUEPRINTS)
    ap.add_argument("--n-per-type", type=int, default=N_PER_TYPE)
    ap.add_argument("--task-types", default=None,
                    help="逗号分隔任务类型过滤（默认全部 3 种：motif_family,hub,reachability）")
    ap.add_argument("--max-calls", type=int, default=500)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--skip-llm", action="store_true",
                    help="只生成蓝图清单，不跑 LLM（调试用）")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--workers", type=int, default=3,
                    help="并发 worker 数（默认 3，对齐 SenseNova KeyPool 3-key）")
    ap.add_argument("--timeout", type=float, default=90,
                    help="每个 agent chat() 的超时秒数（默认 90）")
    ap.add_argument("--max-retries", type=int, default=1,
                    help="单个 chat 失败重试次数（默认 1）")
    args = ap.parse_args()

    # 任务类型过滤：默认全部 3 种，或逗号分隔子集
    if args.task_types:
        tt = tuple(t.strip() for t in args.task_types.split(",") if t.strip())
        invalid = [t for t in tt if t not in TASK_TYPES]
        if invalid:
            ap.error(f"unknown task_type(s): {invalid}; valid: {TASK_TYPES}")
        active_task_types = tt
    else:
        active_task_types = TASK_TYPES

    log("=" * 72)
    log("D-1 P1 结案实验 · LLM 编排基底对照")
    log("=" * 72)
    log(f"base_url     = {args.base_url}")
    log(f"model        = {args.model}")
    log(f"n_blueprints = {args.n_blueprints}")
    log(f"n_per_type   = {args.n_per_type}")
    log(f"topologies   = {TOPOLOGIES}")
    log(f"task_types   = {active_task_types}")
    log(f"seed         = {args.seed}")
    log(f"workers      = {args.workers}")
    log("")

    # ---------------------------------------------------------- 蓝图
    rng = random.Random(args.seed)
    blueprints = build_blueprints(rng, args.n_blueprints)
    n_ev = sum(1 for bp in blueprints if bp.origin == "evidence")
    n_rn = len(blueprints) - n_ev
    motif_dist: dict[str, int] = {}
    for bp in blueprints:
        motif_dist[bp.motif_family] = motif_dist.get(bp.motif_family, 0) + 1
    log(f"blueprints: {len(blueprints)} total  (evidence={n_ev}, random={n_rn})")
    log(f"motif distribution: {motif_dist}")

    # ---------------------------------------------------------- 任务
    all_tasks = []
    for bp in blueprints:
        tasks = generate_tasks(
            bp,
            task_types=active_task_types,
            n_per_type=args.n_per_type,
            rng=random.Random(args.seed + (hash(bp.name) % 10000)),
        )
        for t in tasks:
            all_tasks.append(t)
    log(f"tasks generated: {len(all_tasks)}  "
        f"(= {len(blueprints)} bp × {args.n_per_type} × {len(active_task_types)})")

    # ---------------------------------------------------------- 后端
    if args.skip_llm:
        log("[SKIP LLM] — writing blueprint manifest only")
        manifest = {
            "seed": args.seed,
            "n_blueprints": args.n_blueprints,
            "n_ev": n_ev,
            "n_rn": n_rn,
            "motif_distribution": motif_dist,
            "blueprints": [
                {"name": bp.name, "origin": bp.origin,
                 "motif_family": bp.motif_family,
                 "n_nodes": len(bp.nodes), "n_edges": len(bp.edges)}
                for bp in blueprints
            ],
        }
        RESULT_FILE.write_text(json.dumps(manifest, indent=2,
                                          ensure_ascii=False), encoding="utf-8")
        log(f"wrote {RESULT_FILE}")
        return 0

    backend = HTTPLLMBackend(
        base_url=args.base_url, model=args.model,
        max_tokens=128, temperature=0.0, seed=args.seed,
        reasoning_effort="none",
        timeout_s=args.timeout,   # 每 agent call 的超时
        max_retries=args.max_retries,
    )

    # ---------------------------------------------------------- 探测
    log("LLM smoke test ...")
    t0 = time.perf_counter()
    try:
        r = backend.chat("You are helpful.", "Reply with just: OK")
        log(f"  smoke OK ({time.perf_counter() - t0:.2f}s): {r[:60]!r}")
    except Exception as e:
        log(f"  [FATAL] smoke test failed: {e}")
        return 2

    # ---------------------------------------------------------- 并发跑
    # 采样策略：先做完整 (task, topology) 网格，再按固定 seed shuffle，
    # 取前 N。这样 work[:N] 均匀覆盖 evidence/random 和 4 种拓扑。
    work_full = [(t, topo) for t in all_tasks for topo in TOPOLOGIES]
    work_rng = random.Random(args.seed ^ 0xD1C1)  # 独立采样 seed
    work_rng.shuffle(work_full)
    work = work_full[:args.max_calls] if args.max_calls < len(work_full) else work_full
    if len(work) < len(work_full):
        log(f"[WARN] capping {len(work_full)} -> {len(work)} calls")
    # 覆盖率诊断
    from collections import Counter
    origins_hit = Counter()
    topologies_hit = Counter()
    bps_hit = set()
    for t, topo in work:
        origins_hit[t.blueprint.origin] += 1
        topologies_hit[topo] += 1
        bps_hit.add(t.id.split("|")[0])
    log(f"sample coverage: origins={dict(origins_hit)}, "
        f"topologies={dict(topologies_hit)}, n_blueprints_hit={len(bps_hit)}")

    log(f"total orchestration calls: {len(work)}")
    t_start = time.perf_counter()
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {}
        for task, topo in work:
            fut = ex.submit(
                run_single,
                backend, task.id, topo,
                task.prompt, task.ground_truth, task.task_type,
            )
            futures[fut] = (task.id, topo)

        done = 0
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                res = {"task_id": key[0], "topology": key[1],
                       "task_type": "?", "correct": False,
                       "error": f"{type(e).__name__}: {str(e)[:200]}"}
            results.append(res)
            done += 1
            if done % 50 == 0 or done == len(work):
                elapsed = time.perf_counter() - t_start
                acc = sum(1 for r in results if r.get("correct")) / len(results)
                log(f"  {done}/{len(work)}  ({elapsed:.1f}s)  acc={acc:.3f}")

    elapsed = time.perf_counter() - t_start
    log(f"done: {len(results)} results in {elapsed:.1f}s "
        f"({len(results)/elapsed:.1f} calls/s)")

    # ---------------------------------------------------------- 分析
    log("")
    log("=" * 72)
    log("分析 · per (topology, origin) accuracy")
    log("=" * 72)
    table, verdicts, overall = analyse(results, blueprints)

    # ---------------------------------------------------------- 落盘
    out = {
        "meta": {
            "run_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "seed": args.seed,
            "model": args.model,
            "base_url": args.base_url,
            "n_blueprints": args.n_blueprints,
            "n_ev": n_ev,
            "n_rn": n_rn,
            "n_per_type": args.n_per_type,
            "task_types": list(active_task_types),
            "topologies": list(TOPOLOGIES),
            "margin_pp": MARGIN_PP,
            "significance_alpha": SIGNIFICANCE_ALPHA,
            "total_calls": len(work),
            "wall_clock_s": round(elapsed, 2),
            "blueprint_spec": BLUEPRINT_SPEC,
        },
        "motif_distribution": motif_dist,
        "overall_verdict": overall,
        "per_topo_origin_accuracy": table,
        "significance_tests": verdicts,
        "results": results,
    }
    RESULT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False,
                                      default=str), encoding="utf-8")
    log(f"wrote {RESULT_FILE}")
    return 0 if overall else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("[INTERRUPTED]")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        log(f"[FATAL] {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
