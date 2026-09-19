"""
Phase 1 基准测试：模块堆叠优势验证

目标：验证新模块（attention + working_memory）和新蓝图（attention_gate /
working_memory_buffer / attention_working_combo）是否能超越旧模块/蓝图。

测试设计：
- 5 配置：baseline（4 模块无蓝图）/ sequential（4 模块+旧蓝图）/
  attention_gate（6 模块+新蓝图）/ working_memory_buffer（6 模块+新蓝图）/
  attention_working_combo（6 模块+新组合蓝图）
- 5 场景：SwarmLabs 已有场景（surrogate_forrester / microbio_monod /
  chem_langmuir / llm_scaling / bio_logistic）
- 3 轮重复
- 指标：wall_ms / score / converged / n_agents / n_edges / n_modules

验证目标：
1. 新模块/蓝图是否正确生成
2. 新配置是否稳定运行
3. 是否有结构性优势（如更少的 fallback、更好的路由）

用法：
    python benchmark_module_stacking.py                # 跑全部
    python benchmark_module_stacking.py --quick        # 只跑 2 场景（快速验证）
    python benchmark_module_stacking.py --n-repeats 5  # 5 轮重复
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ====================================================================== #
# 路径配置
# ====================================================================== #
SWARMLABS = r"C:\Users\xing\Desktop\swarmlabs"
FLYBRAIN_BP = (
    r"C:\Users\xing\Desktop\flybrain-connectome"
    r"\flybrain-connectome-mcp\generated_organisms\swarmlabs"
)
PYTHON = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"
FLYBRAIN_DATA_DIR = r"C:\Users\xing\Desktop\flybrain-connectome\male_cns"
FLYBRAIN_API_KEY = "flybrain_dfacd1184a8d21ba263d282a54b425d0d06b67fd50b2438c90e219edfff73cb5"
RESULTS_DIR = Path(r"C:\Users\xing\Desktop\flybrain-connectome\integrations\swarmlabs")
CSV_PATH = RESULTS_DIR / "benchmark_module_stacking.csv"
REPORT_PATH = RESULTS_DIR / "MODULE_STACKING_REPORT.md"

# ====================================================================== #
# 配置定义
# ====================================================================== #
# 5 配置：baseline / sequential / attention_gate / working_memory_buffer /
# attention_working_combo
CONFIGS = [
    ("baseline", None, 4, False),           # 4 模块，无蓝图
    ("sequential", "sequential", 4, False), # 4 模块，旧蓝图
    ("attention_gate", "attention_gate", 6, True),  # 6 模块，新蓝图
    ("working_memory_buffer", "working_memory_buffer", 6, True),  # 6 模块，新蓝图
    ("attention_working_combo", "attention_working_combo", 6, True),  # 6 模块，新组合蓝图
]

# 5 场景（SwarmLabs 已有）
SCENARIOS = [
    "surrogate_forrester",
    "microbio_monod",
    "chem_langmuir",
    "llm_scaling",
    "bio_logistic",
]

# ====================================================================== #
# 拓扑文件生成
# ====================================================================== #
def generate_topology(config_name: str, blueprint_name: str | None,
                      n_modules: int) -> str:
    """Generate a .swarm.json topology file for a given config.

    Returns the path to the generated file.
    """
    import sys
    sys.path.insert(0, r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp")
    import synthetic_bio_topology as c1

    # Resolve motifs (local snapshot, offline)
    doc = c1.resolve_motifs(source="local")

    # Build spec
    spec = {
        "n_modules": n_modules,
        "agents_per_module": 4,
        "module_profiles": "cycled",
        "blueprint": blueprint_name,
    }

    # Design organism
    org = c1.design_organism(spec, motifs=doc, seed=7)

    # Build SwarmLabs config (provenance is built internally by _motif_provenance)
    cfg = c1.build_swarmlabs_config(org, name=f"bench_{config_name}")

    # Write .swarm.json
    fp = Path(FLYBRAIN_BP) / f"bench_{config_name}.swarm.json"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(fp)


# ====================================================================== #
# 运行单个场景
# ====================================================================== #
def run_once(scenario: str, config_name: str, blueprint_name: str | None,
             n_modules: int) -> dict:
    """Run a single scenario with a given config.

    Returns a dict with:
        scenario, config, blueprint, n_modules, wall_ms, score, converged,
        n_agents, n_edges, is_bio_prior, error (if any)
    """
    # Generate topology file (if needed)
    topo_file = generate_topology(config_name, blueprint_name, n_modules)

    # Build request JSON (mirrors e2e_bio_advantage.py)
    req = {
        "goal": f"模块堆叠验证 {scenario} / {config_name}",
        "scenarios": [scenario],
        "max_scenarios": 1,
        "top_n": 5,
        "allow_correction": True,
        "thresholds": {
            "rel_converged": 0.05,
            "cov_min": 0.8,
            "cal_max": 0.08,
        },
    }
    req_path = Path(SWARMLABS) / "agentteams" / "samples" / f"_bench_{scenario}_{config_name}.json"
    req_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build command: run.py --request (NOT runner.py --scenario, which returns immediately)
    cmd = [PYTHON, str(Path(SWARMLABS) / "agentteams" / "run.py"),
           "--request", str(req_path), "--no-local-model"]
    if topo_file and Path(topo_file).exists():
        cmd.extend(["--topology", topo_file])

    # Run the command with proper env
    env = os.environ.copy()
    env["FLYBRAIN_DATA_DIR"] = FLYBRAIN_DATA_DIR
    env["FLYBRAIN_API_KEY"] = FLYBRAIN_API_KEY
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env.pop(k, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"

    start = time.time()
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
            cwd=SWARMLABS,
            env=env,
        )
        wall_ms = int((time.time() - start) * 1000)
    except subprocess.TimeoutExpired:
        wall_ms = int((time.time() - start) * 1000)
        return _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, "timeout")
    except Exception as e:
        wall_ms = int((time.time() - start) * 1000)
        return _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, str(e))

    # Read latest run result (mirrors e2e_bio_advantage.py)
    runs_dir = Path(SWARMLABS) / "agentteams" / "runs"
    if not runs_dir.exists():
        return _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, "runs_dir_not_found")
    runs = sorted(runs_dir.iterdir())
    if not runs:
        return _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, "no_run")
    latest = runs[-1]
    result_path = latest / "result.json"
    if not result_path.exists():
        return _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, "no_result_json")
    try:
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, f"json_parse_error: {e}")

    # Extract metrics
    lr = data.get("loop_report", {}) or {}
    ev = lr.get("evaluate", {}) or {}

    score = ev.get("team_score")
    converged = ev.get("converged_ratio")

    # Convert converged_ratio from "X/Y" string to float
    if isinstance(converged, str):
        parts = converged.split("/")
        if len(parts) == 2:
            try:
                converged = float(parts[0]) / float(parts[1])
            except Exception:
                converged = None

    # Count agents and edges from topology_source
    n_agents = 0
    n_edges = 0
    is_bio_prior = None
    topo_src = lr.get("topology_source", {})
    if topo_src:
        n_agents = topo_src.get("n_agents", 0)
        n_edges = topo_src.get("n_edges", 0)
        mp = topo_src.get("motif_provenance", {})
        if mp:
            is_bio_prior = mp.get("is_bio_prior")

    # Fallback: count from swarm
    if n_agents == 0:
        swarm = data.get("swarm", {})
        agents = swarm.get("agents", [])
        edges = swarm.get("edges", [])
        n_agents = len(agents)
        n_edges = len(edges)
        mp = swarm.get("motif_provenance", {})
        if mp and is_bio_prior is None:
            is_bio_prior = mp.get("is_bio_prior")

    # Also read is_bio_prior directly from the topology file (SwarmLabs may not propagate it)
    if is_bio_prior is None and topo_file and Path(topo_file).exists():
        try:
            tdoc = json.loads(Path(topo_file).read_text(encoding="utf-8"))
            mp = tdoc.get("motif_provenance", {})
            if mp:
                is_bio_prior = mp.get("is_bio_prior")
        except Exception:
            pass

    return {
        "scenario": scenario,
        "config": config_name,
        "blueprint": blueprint_name or "none",
        "n_modules": n_modules,
        "wall_ms": wall_ms,
        "score": score,
        "converged": converged,
        "n_agents": n_agents,
        "n_edges": n_edges,
        "is_bio_prior": is_bio_prior,
        "error": None,
    }


def _empty_result(scenario, config_name, blueprint_name, n_modules, wall_ms, error):
    return {
        "scenario": scenario,
        "config": config_name,
        "blueprint": blueprint_name or "none",
        "n_modules": n_modules,
        "wall_ms": wall_ms,
        "score": None,
        "converged": None,
        "n_agents": 0,
        "n_edges": 0,
        "is_bio_prior": None,
        "error": error,
    }


# ====================================================================== #
# 主函数
# ====================================================================== #
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-repeats", type=int, default=3,
                        help="Number of repeats per scenario-config combo")
    parser.add_argument("--quick", action="store_true",
                        help="Run only 2 scenarios (quick validation)")
    args = parser.parse_args()

    n_rep = args.n_repeats
    scenarios = SCENARIOS[:2] if args.quick else SCENARIOS

    print("模块堆叠优势验证基准测试")
    print(f"配置: {len(scenarios)} 场景 × {len(CONFIGS)} 配置 × {n_rep} 轮 "
          f"= {len(scenarios) * len(CONFIGS) * n_rep} 样本")
    print(f"场景: {scenarios}")
    print(f"配置: {[c[0] for c in CONFIGS]}")
    print(f"预计时间: {len(scenarios) * len(CONFIGS) * n_rep * 5} 秒（每次约 5s）")
    print()

    results = []

    # Run all combos
    for i, sc in enumerate(scenarios):
        print(f"[{i+1}/{len(scenarios)}] {sc}")
        for config_name, bp_name, n_mod, is_new in CONFIGS:
            for rep in range(n_rep):
                tag = f"{sc} / {config_name} / rep{rep+1}"
                r = run_once(sc, config_name, bp_name, n_mod)
                results.append(r)
                err = f" ERR={r.get('error')}" if r.get("error") else ""
                new_marker = " [NEW]" if is_new else ""
                print(f"  {tag:55s} wall={r['wall_ms']:>5d}ms "
                      f"score={r['score']} converged={r['converged']} "
                      f"n={r['n_agents']}/{r['n_edges']} "
                      f"mod={r['n_modules']} "
                      f"bio={r['is_bio_prior']}{new_marker}{err}")

    # Write CSV
    fieldnames = ["scenario", "config", "blueprint", "n_modules", "wall_ms",
                  "score", "converged", "n_agents", "n_edges", "is_bio_prior",
                  "error"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nCSV 写入: {CSV_PATH}")

    # Print summary
    print("\n" + "=" * 100)
    print("统计汇总（3 轮重复）")
    print("=" * 100)

    # Group by (scenario, config)
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in results:
        key = (r["scenario"], r["config"])
        grouped[key].append(r)

    # Print summary table
    print(f"{'scenario':<30} {'config':<30} {'wall_ms':>12} {'score':>12} "
          f"{'converged':>10} {'n_agents':>10} {'is_bio':>8}")
    print("-" * 100)

    for (sc, cfg), rs in sorted(grouped.items()):
        walls = [r["wall_ms"] for r in rs if r["wall_ms"] is not None]
        scores = [r["score"] for r in rs if r["score"] is not None]
        convs = [r["converged"] for r in rs if r["converged"] is not None]
        agents = [r["n_agents"] for r in rs if r["n_agents"] is not None]
        edges = [r["n_edges"] for r in rs if r["n_edges"] is not None]
        bios = [r["is_bio_prior"] for r in rs if r["is_bio_prior"] is not None]

        wall_mean = sum(walls) / len(walls) if walls else 0
        score_mean = sum(scores) / len(scores) if scores else 0
        conv_mean = sum(convs) / len(convs) if convs else 0
        agents_mean = sum(agents) / len(agents) if agents else 0
        edges_mean = sum(edges) / len(edges) if edges else 0
        bio_str = str(bios[0]) if bios else "?"

        print(f"{sc:<30} {cfg:<30} {wall_mean:>10.0f}ms {score_mean:>10.1f} "
              f"{conv_mean:>10.3f} {agents_mean:>8.0f} {bio_str:>8}")

    # Compare new vs old configs
    print("\n" + "=" * 100)
    print("关键对比：新配置（6 模块）vs 旧配置（4 模块）")
    print("=" * 100)

    # Group by scenario
    by_scenario = defaultdict(dict)
    for (sc, cfg), rs in grouped.items():
        walls = [r["wall_ms"] for r in rs if r["wall_ms"] is not None]
        scores = [r["score"] for r in rs if r["score"] is not None]
        if walls and scores:
            by_scenario[sc][cfg] = {
                "wall_mean": sum(walls) / len(walls),
                "score_mean": sum(scores) / len(scores),
            }

    for sc in scenarios:
        if sc not in by_scenario:
            continue
        configs = by_scenario[sc]
        print(f"\n{sc}:")
        print(f"  {'config':<30} {'wall_ms':>10} {'score':>10}")
        print(f"  {'-'*50}")
        for cfg, metrics in sorted(configs.items()):
            print(f"  {cfg:<30} {metrics['wall_mean']:>10.0f} "
                  f"{metrics['score_mean']:>10.1f}")

        # Compare baseline vs new
        if "baseline" in configs and "attention_gate" in configs:
            baseline_wall = configs["baseline"]["wall_mean"]
            new_wall = configs["attention_gate"]["wall_mean"]
            delta = (new_wall - baseline_wall) / baseline_wall * 100 if baseline_wall else 0
            print(f"  attention_gate vs baseline: wall Δ={delta:+.1f}%")

        if "baseline" in configs and "working_memory_buffer" in configs:
            baseline_wall = configs["baseline"]["wall_mean"]
            new_wall = configs["working_memory_buffer"]["wall_mean"]
            delta = (new_wall - baseline_wall) / baseline_wall * 100 if baseline_wall else 0
            print(f"  working_memory_buffer vs baseline: wall Δ={delta:+.1f}%")

        if "baseline" in configs and "attention_working_combo" in configs:
            baseline_wall = configs["baseline"]["wall_mean"]
            new_wall = configs["attention_working_combo"]["wall_mean"]
            delta = (new_wall - baseline_wall) / baseline_wall * 100 if baseline_wall else 0
            print(f"  attention_working_combo vs baseline: wall Δ={delta:+.1f}%")

    # Write report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# 模块堆叠优势验证报告\n\n")
        f.write(f"**日期**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**配置**：{len(scenarios)} 场景 × {len(CONFIGS)} 配置 × {n_rep} 轮 "
                f"= {len(scenarios) * len(CONFIGS) * n_rep} 样本\n\n")
        f.write(f"## 实验设计\n\n")
        f.write(f"| 配置 | 模块数 | 蓝图 | 新/旧 |\n")
        f.write(f"|---|---|---|---|\n")
        for cfg_name, bp, n_mod, is_new in CONFIGS:
            marker = "新" if is_new else "旧"
            f.write(f"| {cfg_name} | {n_mod} | {bp or '无'} | {marker} |\n")
        f.write(f"\n## 结果汇总\n\n")
        f.write(f"（见 CSV：{CSV_PATH.name}）\n\n")
        f.write(f"## 关键对比\n\n")
        f.write(f"（见上方终端输出）\n")

    print(f"\n报告写入: {REPORT_PATH}")


if __name__ == "__main__":
    main()