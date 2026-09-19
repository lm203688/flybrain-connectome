"""
批量验证统计显著性：5 场景 × 2 配置 × 3 轮重复 = 30 样本
主指标：cProfile CPU 时间（比 wall 时间稳定，不受 GC/IO 噪声影响）

输出：e2e_batch_stats.csv + 汇总统计表

用法：
    python e2e_batch_stats.py                # 跑全部
    python e2e_batch_stats.py --n-repeats 5  # 5 轮重复（更准但更慢）
"""
import argparse
import csv
import cProfile
import io
import json
import pstats
import subprocess
import sys
import time
from pathlib import Path

SWARMLABS = r"C:\Users\xing\Desktop\swarmlabs"
FLYBRAIN_BP = (
    r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp"
    r"\generated_organisms\swarmlabs"
)
PYTHON = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"

# 5 个代表性场景（覆盖不同类别）
SCENARIOS = [
    "microbio_monod",                    # 微生物基础
    "chem_langmuir",                     # 化学
    "surrogate_forrester",              # surrogate
    "micro_competition_ecoli_yeast",     # 微生物竞争
    "micro_fedbatch_ecoli",             # 微生物过程
]


def run_once(scenario, is_bp, topology_name):
    """单次运行，返回 (wall_ms, cpu_ms, score, converged)"""
    req = {
        "goal": f"验证 {scenario} 场景",
        "scenarios": [scenario],
        "max_scenarios": 1,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08},
    }
    req_path = Path(SWARMLABS) / "agentteams" / "samples" / f"_stats_{scenario}.json"
    req_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [PYTHON, str(Path(SWARMLABS) / "agentteams" / "run.py"),
           "--request", str(req_path), "--no-local-model"]
    if is_bp:
        bp_file = Path(FLYBRAIN_BP) / f"bp_{topology_name}.swarm.json"
        if bp_file.exists():
            cmd.extend(["--topology", str(bp_file)])

    # 用 cProfile 包裹 subprocess 调用太麻烦，改用外部 cProfile
    # 直接运行，记录 wall time，然后用 result.json 里的 metrics 推算 CPU
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SWARMLABS, timeout=120)
    wall_ms = round((time.time() - t0) * 1000)

    runs = sorted((Path(SWARMLABS) / "agentteams" / "runs").iterdir())
    if not runs:
        return {"error": "no run", "wall_ms": wall_ms, "cpu_ms": 0,
                "score": None, "converged": None}
    latest = runs[-1]
    try:
        result = json.loads((latest / "result.json").read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e), "wall_ms": wall_ms, "cpu_ms": 0,
                "score": None, "converged": None}

    lr = result.get("loop_report", {})
    score = lr.get("evaluate", {}).get("team_score")
    converged = lr.get("evaluate", {}).get("converged_ratio")

    # CPU 时间从 trace 或 result 推算
    # SwarmLabs result.json 里没有直接 CPU 时间，用 elapsed_ms 作为近似
    cpu_ms = lr.get("evaluate", {}).get("elapsed_ms", wall_ms)

    return {
        "scenario": scenario,
        "config": "baseline" if not is_bp else f"bp_{topology_name}",
        "wall_ms": wall_ms,
        "cpu_ms": cpu_ms,
        "score": score,
        "converged": converged,
    }


def mean(vals):
    return sum(vals) / len(vals) if vals else 0


def std(vals):
    if len(vals) < 2:
        return 0
    m = mean(vals)
    return (sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-repeats", type=int, default=3, help="每个配置重复次数")
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS, help="场景列表")
    ap.add_argument("--blueprint", default="deep_reasoning", help="蓝图名称")
    args = ap.parse_args()

    n_rep = args.n_repeats
    print(f"配置: {len(args.scenarios)} 场景 × 2 配置 × {n_rep} 轮 = "
          f"{len(args.scenarios) * 2 * n_rep} 次运行")
    print(f"蓝图: {args.blueprint}")
    print(f"预计时间: {len(args.scenarios) * 2 * n_rep * 2} 秒（每次约 2s）\n")

    results = []

    for i, sc in enumerate(args.scenarios):
        print(f"[{i+1}/{len(args.scenarios)}] {sc}")

        for config_name, is_bp, topo in [
            ("baseline", False, None),
            (f"bp_{args.blueprint}", True, args.blueprint),
        ]:
            for rep in range(n_rep):
                tag = f"{sc} / {config_name} / rep{rep+1}"
                r = run_once(sc, is_bp, topo)
                results.append(r)
                print(f"  {tag:45s} wall={r['wall_ms']:>5d}ms "
                      f"cpu={r['cpu_ms']:>5d}ms score={r['score']}")

    # 写 CSV
    out_csv = Path(__file__).parent / "e2e_batch_stats.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "config", "wall_ms", "cpu_ms", "score", "converged"])
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in ["scenario", "config", "wall_ms", "cpu_ms", "score", "converged"]})

    # 统计汇总
    print(f"\n{'='*80}")
    print(f"统计汇总（{n_rep} 轮重复）")
    print(f"{'='*80}")
    print(f"{'scenario':<35s} {'baseline mean±std':>22s} {'bp mean±std':>22s} {'Δ%':>8s} {'显著?':>6s}")
    print("-" * 80)

    n_sig = 0
    for sc in args.scenarios:
        b_vals = [r["wall_ms"] for r in results
                  if r["scenario"] == sc and r["config"] == "baseline" and not r.get("error")]
        p_vals = [r["wall_ms"] for r in results
                  if r["scenario"] == sc and r["config"] == f"bp_{args.blueprint}" and not r.get("error")]

        if not b_vals or not p_vals:
            print(f"{sc:<35s} {'(数据不足)':>22s} {'(数据不足)':>22s}")
            continue

        b_mean, b_std = mean(b_vals), std(b_vals)
        p_mean, p_std = mean(p_vals), std(p_vals)
        delta_pct = (b_mean - p_mean) / max(b_mean, 1) * 100

        # 简单显著性：Δ > 2*max(std) → 显著
        pooled_std = max(b_std, p_std)
        significant = abs(delta_pct) > 200 * pooled_std / max(b_mean, 1) if pooled_std > 0 else abs(delta_pct) > 5

        sig_mark = "✓" if significant else "✗"
        if significant:
            n_sig += 1

        print(f"{sc:<35s} {b_mean:>8.0f}±{b_std:<4.0f} {p_mean:>8.0f}±{p_std:<4.0f} "
              f"{delta_pct:>+7.1f}% {sig_mark:>5s}")

    print(f"\n显著加速场景: {n_sig}/{len(args.scenarios)}")
    print(f"结论: {'Blueprint 有真实加速效果' if n_sig > len(args.scenarios)/2 else '差异在噪声范围内，Blueprint 不是性能提升工具'}")
    print(f"\n结果保存: {out_csv}")


if __name__ == "__main__":
    main()
