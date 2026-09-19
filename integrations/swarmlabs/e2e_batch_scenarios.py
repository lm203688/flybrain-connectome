"""
批量场景验证：10 个代表性 v3 场景 × (baseline + bp_deep_reasoning)
单场景任务（max_scenarios=1），控制总时间在 5 分钟内

输出：C:/Users/xing/Desktop/flybrain-connectome/integrations/swarmlabs/e2e_batch_results.csv
"""
import argparse
import csv
import json
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

# 10 个代表性场景（覆盖不同域和模式）
SCENARIOS = [
    "surrogate_forrester",       # surrogate
    "chem_langmuir",             # chem
    "microbio_monod",            # micro cross
    "pde_heat1d",                # pde
    "micro_ecoli_glucose",       # micro basic growth
    "micro_fedbatch_ecoli",      # micro process
    "micro_competition_ecoli_yeast",  # micro compete
    "micro_antibiotic_timekill", # micro antibiotic
    "micro_tessier_ecoli",       # micro interaction
    "micro_crabtree_cerevisiae", # micro metabolic
]

BLUEPRINT = "deep_reasoning"  # 用实测最常用的一种


def run_one(scenario, is_bp):
    req = {
        "goal": f"验证 {scenario} 场景",
        "scenarios": [scenario],
        "max_scenarios": 1,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08},
    }
    req_path = Path(SWARMLABS) / "agentteams" / "samples" / f"_e2e_batch_{scenario}.json"
    req_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        PYTHON, str(Path(SWARMLABS) / "agentteams" / "run.py"),
        "--request", str(req_path), "--no-local-model",
    ]
    if is_bp:
        cmd.extend(["--topology", str(Path(FLYBRAIN_BP) / f"bp_{BLUEPRINT}.swarm.json")])

    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SWARMLABS, timeout=120)
    elapsed = time.time() - t0

    runs = sorted((Path(SWARMLABS) / "agentteams" / "runs").iterdir())
    if not runs:
        return {"error": "no run"}
    latest = runs[-1]
    try:
        result = json.loads((latest / "result.json").read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}

    return {
        "scenario": scenario,
        "config": "baseline" if not is_bp else f"bp_{BLUEPRINT}",
        "elapsed_ms": round(elapsed * 1000),
        "score": result.get("loop_report", {}).get("evaluate", {}).get("team_score"),
        "converged": result.get("loop_report", {}).get("evaluate", {}).get("converged_ratio"),
        "spans": result.get("loop_report", {}).get("analyze", {}).get("spans"),
        "errors": result.get("loop_report", {}).get("analyze", {}).get("errors"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blueprint", default="deep_reasoning", help="蓝图名称")
    args = ap.parse_args()
    global BLUEPRINT
    BLUEPRINT = args.blueprint

    results = []
    for sc in SCENARIOS:
        print(f"[1/2] baseline: {sc}", end=" ", flush=True)
        r1 = run_one(sc, False)
        print(f"→ {r1.get('elapsed_ms')}ms score={r1.get('score')} conv={r1.get('converged')}")
        results.append(r1)
        print(f"[2/2] bp_{BLUEPRINT}: {sc}", end=" ", flush=True)
        r2 = run_one(sc, True)
        print(f"→ {r2.get('elapsed_ms')}ms score={r2.get('score')} conv={r2.get('converged')}")
        results.append(r2)

    # 写 CSV
    out_path = Path(__file__).parent / "e2e_batch_results.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "config", "elapsed_ms", "score", "converged", "spans", "errors"])
        w.writeheader()
        w.writerows(results)

    # 汇总
    print(f"\n{'='*70}")
    print(f"{'scenario':<35s} {'baseline':>20s} {'bp_deep_reasoning':>20s} {'speedup':>8s}")
    print("-" * 70)
    for i in range(0, len(results), 2):
        b, p = results[i], results[i + 1]
        if b.get("error") or p.get("error"):
            print(f"{b['scenario']:<35s} {str(b.get('error')):>20s} {str(p.get('error')):>20s}")
            continue
        speedup = (b["elapsed_ms"] - p["elapsed_ms"]) / max(b["elapsed_ms"], 1) * 100
        print(f"{b['scenario']:<35s} {b['elapsed_ms']:>8d}ms/{b['score']:>5} {p['elapsed_ms']:>8d}ms/{p['score']:>5} {speedup:>7.1f}%")

    # 汇总统计
    print("-" * 70)
    n_bp = sum(1 for i in range(1, len(results), 2)
               if not results[i].get("error") and not results[i-1].get("error"))
    n_speedup = sum(1 for i in range(1, len(results), 2)
                    if not results[i].get("error") and not results[i-1].get("error")
                    and results[i]["elapsed_ms"] < results[i-1]["elapsed_ms"])
    n_same_score = sum(1 for i in range(1, len(results), 2)
                       if not results[i].get("error") and not results[i-1].get("error")
                       and results[i]["score"] == results[i-1]["score"])
    print(f"总计 {n_bp} 组对比：{n_speedup} 组加速 / {n_bp - n_speedup} 组持平或变慢")
    print(f"正确性一致（score 相同）：{n_same_score}/{n_bp} 组")
    print(f"结果保存：{out_path}")


if __name__ == "__main__":
    main()
