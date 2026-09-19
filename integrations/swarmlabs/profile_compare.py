"""
cProfile 剖析：baseline vs bp_deep_reasoning
选 chem_langmuir（-10.4% 变慢最明显的单场景）

策略：用 python -m cProfile -o out.prof run.py [args]
"""
import cProfile
import json
import pstats
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SWARMLABS = r"C:\Users\xing\Desktop\swarmlabs"
FLYBRAIN_BP = (
    r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp"
    r"\generated_organisms\swarmlabs"
)
PYTHON = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"

SCENARIO = "chem_langmuir"


def run_profiled(is_bp, profile_out):
    req = {
        "goal": f"profile {SCENARIO}",
        "scenarios": [SCENARIO],
        "max_scenarios": 1,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08},
    }
    req_path = Path(SWARMLABS) / "agentteams" / "samples" / f"_profile_{SCENARIO}.json"
    req_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        PYTHON, "-m", "cProfile", "-o", str(profile_out),
        str(Path(SWARMLABS) / "agentteams" / "run.py"),
        "--request", str(req_path),
        "--no-local-model",
    ]
    if is_bp:
        cmd.extend(["--topology", str(Path(FLYBRAIN_BP) / "bp_deep_reasoning.swarm.json")])

    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SWARMLABS, timeout=120)
    elapsed = time.time() - t0
    return r, elapsed


def show_top(label, profile_out, n=20):
    print(f"\n{'='*80}")
    print(f"{label}  ·  profile: {profile_out}")
    print(f"{'='*80}")
    ps = pstats.Stats(profile_out)
    ps.strip_dirs().sort_stats("cumtime")
    ps.print_stats(n)
    return ps


def main():
    import time
    with tempfile.TemporaryDirectory() as tmp:
        bp_baseline = Path(tmp) / "baseline.prof"
        bp_bp = Path(tmp) / "blueprint.prof"

        print(f"Profiling baseline ({SCENARIO})...", end=" ", flush=True)
        r1, t1 = run_profiled(False, str(bp_baseline))
        if r1.returncode != 0:
            print(f"FAILED rc={r1.returncode}")
            print(r1.stderr[-500:])
            return
        print(f"ok (wall {t1:.2f}s)")

        print(f"Profiling bp_deep_reasoning ({SCENARIO})...", end=" ", flush=True)
        r2, t2 = run_profiled(True, str(bp_bp))
        if r2.returncode != 0:
            print(f"FAILED rc={r2.returncode}")
            print(r2.stderr[-500:])
            return
        print(f"ok (wall {t2:.2f}s)")

        ps_b = show_top("BASELINE (cumtime top 20)", str(bp_baseline))
        ps_p = show_top("BLUEPRINT bp_deep_reasoning (cumtime top 20)", str(bp_bp))

        # 总时间对比
        print(f"\n{'='*80}")
        print(f"总 CPU 时间对比")
        print(f"{'='*80}")
        print(f"  baseline  CPU: {ps_b.total_tt:.3f}s   wall: {t1:.2f}s")
        print(f"  blueprint CPU: {ps_p.total_tt:.3f}s   wall: {t2:.2f}s")
        if ps_b.total_tt > 0:
            cpu_delta = (ps_p.total_tt - ps_b.total_tt) / ps_b.total_tt * 100
            print(f"  CPU 差异: {cpu_delta:+.1f}%")
        if t1 > 0:
            wall_delta = (t2 - t1) / t1 * 100
            print(f"  wall 差异: {wall_delta:+.1f}%")

        # 找出 blueprint 独有的高开销（planner 相关）
        print(f"\n{'='*80}")
        print("Blueprint 中的 routing 相关函数（top cumtime）")
        print(f"{'='*80}")
        ps_p.sort_stats("cumtime")
        routing_keywords = ('route', 'blueprint', 'semantic', 'capability', 'planner', 'module')
        # pstats.Stats.stats 是 dict: key=(file, lineno, func), value=(ncalls, tottime, cumtime, prims, prims_ncalls)
        for key, val in ps_p.stats.items():
            file, lineno, funcname = key
            ncalls, tottime, cumtime, prims, prims_ncalls = val
            func_name = f"{file}:{lineno},{funcname}"
            if any(kw in func_name.lower() for kw in routing_keywords):
                if cumtime > 0.05:  # cumtime > 50ms
                    print(f"  {func_name}")
                    print(f"    calls={ncalls:>5d}  cumtime={cumtime:.3f}s  tottime={tottime:.3f}s")


if __name__ == "__main__":
    main()
