"""
E2E 跨域任务对比：baseline (4-agent) vs blueprint topology (43 agents)
3 个任务分别强调：跨域桥接 / 多步推理 / 候选竞争

用法：
  python e2e_cross_domain.py                # 跑全部 3 个任务
  python e2e_cross_domain.py --only bridge  # 只跑某个
  python e2e_cross_domain.py --baseline-only # 只跑 baseline
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SWARMLABS = r"C:\Users\xing\Desktop\swarmlabs"
FLYBRAIN_BP = (
    r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp"
    r"\generated_organisms\swarmlabs"
)
PYTHON = r"C:\Users\xing\.workbubby\binaries\python\envs\minimind\Scripts\python.exe"

# 修正路径笔误
PYTHON = PYTHON.replace("workbubby", "workbuddy")

TASKS = {
    "bridge": {
        "goal": "跨域桥接：将 Surrogate 优化经验应用到化学-微生物动力学建模，识别三个不同物理域中的共性规律",
        "scenarios": ["surrogate_forrester", "chem_langmuir", "microbio_monod"],
        "max_scenarios": 3,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08},
    },
    "deep_reason": {
        "goal": "多步推理：从 PDE 解热方程出发，通过 Surrogate 建模过渡到化学反应器设计，验证跨尺度方法的一致性",
        "scenarios": ["pde_heat1d", "surrogate_hartmann6", "chem_reactor_conversion"],
        "max_scenarios": 3,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08},
    },
    "compete": {
        "goal": "候选竞争：多物种微生物生态系统中竞争者与抗生素响应动力学，评估共存与抑制机制",
        "scenarios": [
            "micro_competition_ecoli_yeast",
            "micro_antibiotic_timekill",
            "micro_tessier_ecoli",
        ],
        "max_scenarios": 3,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08},
    },
}

BLUEPRINTS = [
    ("deep_reasoning", "deep_reasoning"),
    ("competitive", "competitive"),
    ("orchestrated", "orchestrated"),
]


def run_once(task_name, task_id, is_blueprint, bp_name=None):
    """执行一次 agentteams run，返回结构化结果"""
    request_path = Path(SWARMLABS) / "agentteams" / "samples" / f"_e2e_{task_name}_{task_id}.json"
    req = {
        "goal": TASKS[task_name]["goal"],
        "scenarios": TASKS[task_name]["scenarios"],
        "max_scenarios": TASKS[task_name]["max_scenarios"],
        "top_n": TASKS[task_name]["top_n"],
        "allow_correction": TASKS[task_name]["allow_correction"],
        "thresholds": TASKS[task_name]["thresholds"],
    }
    request_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        PYTHON,
        str(Path(SWARMLABS) / "agentteams" / "run.py"),
        "--request", str(request_path),
        "--no-local-model",
    ]
    if is_blueprint:
        bp_file = Path(FLYBRAIN_BP) / f"bp_{bp_name}.swarm.json"
        cmd.append("--topology")
        cmd.append(str(bp_file))

    t0 = time.time()
    r = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=SWARMLABS, timeout=180,
    )
    elapsed = time.time() - t0

    # 解析最新 run
    runs_dir = Path(SWARMLABS) / "agentteams" / "runs"
    runs = sorted(runs_dir.iterdir())
    if not runs:
        return {"error": "no run dir", "elapsed": elapsed}
    latest = runs[-1]
    result = json.loads((latest / "result.json").read_text(encoding="utf-8"))

    # 提取关键指标
    info = {
        "run_id": result.get("run_id"),
        "elapsed_ms": round(elapsed * 1000),
        "team_status": result.get("status"),
        "team_score": result.get("loop_report", {}).get("evaluate", {}).get("team_score"),
        "converged_ratio": result.get("loop_report", {}).get("evaluate", {}).get("converged_ratio"),
        "n_scenarios": len(result.get("loop_report", {}).get("collect", {}).get("scenarios", []))
                       if isinstance(result.get("loop_report", {}).get("collect", {}).get("scenarios"), list)
                       else 0,
        "spans": result.get("loop_report", {}).get("analyze", {}).get("spans"),
        "errors": result.get("loop_report", {}).get("analyze", {}).get("errors"),
        "blocked": result.get("loop_report", {}).get("analyze", {}).get("blocked"),
    }
    # topology_source / blueprint_routing 摘要
    ts = result.get("topology_source")
    if ts:
        info["topology"] = {
            "blueprint": ts.get("blueprint"),
            "n_agents": ts.get("n_agents"),
            "n_modules": ts.get("n_modules"),
            "validation_ok": ts.get("validation_ok"),
        }
    else:
        info["topology"] = None
    # module_routing
    mr = result.get("loop_report", {}).get("module_routing", {})
    if mr:
        info["routed_steps"] = mr.get("summary", {}).get("n_steps_routed")
        info["fallback_steps"] = mr.get("summary", {}).get("n_fallback")
    else:
        info["routed_steps"] = None
        info["fallback_steps"] = None
    return info


def print_summary(task_name, results):
    print(f"\n{'='*80}")
    print(f"TASK: {task_name}  ·  {TASKS[task_name]['goal'][:60]}")
    print(f"{'='*80}")
    print(f"{'config':<28s} {'score':>6s} {'conv':>8s} {'spans':>6s} {'elapsed':>9s} {'routed':>7s} {'fb':>4s}")
    print("-" * 80)
    for label, r in results:
        top = r.get("topology")
        top_str = f"bp={top['blueprint']}" if top else "default-4agent"
        print(
            f"{label:<28s} {str(r.get('team_score')):>6s} "
            f"{str(r.get('converged_ratio')):>8s} {str(r.get('spans')):>6s} "
            f"{r.get('elapsed_ms'):>8d}ms "
            f"{str(r.get('routed_steps')):>7s} {str(r.get('fallback_steps')):>4s}"
        )


def main():
    args = set(sys.argv[1:])
    only = args & set(TASKS.keys())
    task_names = list(only) if only else list(TASKS.keys())
    do_baseline = not args & {"blueprint-only"}
    do_blueprint = not args & {"baseline-only"}

    for task_name in task_names:
        results = []
        if do_baseline:
            print(f"[baseline] task={task_name}", end=" ", flush=True)
            results.append((f"baseline ({task_name})", run_once(task_name, "baseline", False)))
            print("done")

        if do_blueprint:
            for bp, _label in BLUEPRINTS:
                bp_file = Path(FLYBRAIN_BP) / f"bp_{bp}.swarm.json"
                if not bp_file.exists():
                    # 尝试组合蓝图
                    print(f"[blueprint:{bp}] SKIPPED (no file)", end=" ")
                    continue
                print(f"[blueprint:{bp}] task={task_name}", end=" ", flush=True)
                results.append(
                    (f"bp_{bp} ({task_name})", run_once(task_name, f"bp_{bp}", True, bp))
                )
                print("done")

        print_summary(task_name, results)


if __name__ == "__main__":
    main()
