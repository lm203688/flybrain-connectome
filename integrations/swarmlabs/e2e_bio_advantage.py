"""
生物学优势对照实验：10 场景 × 4 配置 × 3 轮 = 120 样本

目的：验证生物学蓝图（bio blueprint）相对 baseline/basic 是否有可测量的优势。
如果 bio blueprint 显著优于 baseline，说明生物学先验转化为了实际价值；
如果不显著，项目定位降级为"审计工具 + 前沿探索"。

4 配置：
  1. baseline          -- 无 blueprint（纯随机拓扑，flybrain 默认）
  2. sequential        -- basic 蓝图（人工前馈链，无生物先验）
  3. competitive_selection -- bio 蓝图（APL body 10540，inhibitory_hub）
  4. deep_reasoning+competitive_selection -- 组合（basic + bio）

10 场景（5 跨域 + 5 微生物代表）：
  跨域：surrogate_forrester / microbio_monod / chem_langmuir / llm_scaling / bio_logistic
  微生物：micro_fedbatch_ecoli / micro_competition_ecoli_yeast / micro_haldane /
          micro_quorum_sensing / micro_antibiotic_tolerance

指标：wall_ms / score / converged / n_agents / n_edges / is_bio_prior / blueprint

用法：
    python e2e_bio_advantage.py                # 跑全部
    python e2e_bio_advantage.py --n-repeats 5  # 5 轮重复（更准但更慢）
    python e2e_bio_advantage.py --quick        # 只跑 3 场景（快速验证）
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

from _local_key import local_api_key  # same-directory helper; keeps keys out of the repo

# ====================================================================== #
# 路径配置
# ====================================================================== #
SWARMLABS = r"C:\Users\xing\Desktop\swarmlabs"
FLYBRAIN_BP = (
    r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp"
    r"\generated_organisms\swarmlabs"
)
PYTHON = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"

# ====================================================================== #
# 场景列表（10 场景 = 5 跨域 + 5 微生物代表）
# ====================================================================== #
SCENARIOS = [
    # 5 跨域（来自 paper_validation_loop.py SCENARIOS）
    "surrogate_forrester",    # 优化（1D Bayesian Optimization）
    "microbio_monod",         # 微生物基础（Monod growth）
    "chem_langmuir",          # 化学（Langmuir 吸附等温线）
    "llm_scaling",            # LLM（Kaplan scaling law）
    "bio_logistic",           # 生物（Logistic growth）
    # 5 微生物代表（来自 microbiology_full.py，选不同机制）
    "micro_fedbatch_ecoli",   # 过程控制（fed-batch）
    "micro_competition_ecoli_yeast",  # 竞争（E.coli vs yeast）
    "micro_haldane",          # 底物抑制（Haldane）
    "micro_quorum_sensing",   # 群体感应
    "micro_antibiotic_tolerance",  # 抗生素耐受
]

# 快速模式（只跑 3 场景）
SCENARIOS_QUICK = [
    "surrogate_forrester",
    "microbio_monod",
    "chem_langmuir",
]

# ====================================================================== #
# 4 配置定义
# ====================================================================== #
# (config_name, blueprint_name_or_None)
CONFIGS = [
    ("baseline", None),                       # 无 blueprint，纯随机拓扑
    ("sequential", "sequential"),             # basic，无生物先验
    ("competitive_selection", "competitive_selection"),  # bio，inhibitory_hub
    ("combo_dr_cs", "deep_reasoning+competitive_selection"),  # 组合
]

# 快速模式（只跑 3 配置）
CONFIGS_QUICK = [
    ("baseline", None),
    ("competitive_selection", "competitive_selection"),
    ("combo_dr_cs", "deep_reasoning+competitive_selection"),
]


def _topology_file(blueprint_name: str | None) -> str | None:
    """Locate the .swarm.json topology file for a given blueprint name.

    For composed blueprints like 'a+b', the filename uses '__' (double underscore)
    instead of '+': bp_a__b.swarm.json

    Returns None if blueprint is None (baseline) or file not found.
    """
    if not blueprint_name:
        return None
    # Replace '+' with '__' for composed blueprint filenames
    file_stem = blueprint_name.replace("+", "__")
    fp = Path(FLYBRAIN_BP) / f"bp_{file_stem}.swarm.json"
    return str(fp) if fp.exists() else None


def _read_bio_prior(blueprint_name: str | None) -> bool | None:
    """Read is_bio_prior from the .swarm.json topology file.

    Returns:
        True if the blueprint has biological prior (motif_provenance.is_bio_prior)
        False if the blueprint is basic (no biological prior)
        None if blueprint is None (baseline) or file not found
    """
    if not blueprint_name:
        return None  # baseline, no blueprint
    topo_file = _topology_file(blueprint_name)
    if not topo_file:
        return None
    try:
        data = json.loads(Path(topo_file).read_text(encoding="utf-8"))
        mp = data.get("motif_provenance", {})
        return mp.get("is_bio_prior")
    except Exception:
        return None


def run_once(scenario: str, blueprint_name: str | None, config_name: str | None = None) -> dict:
    """Run a single scenario with a given blueprint config.

    Returns a dict with:
        scenario, config, blueprint, wall_ms, score, converged,
        n_agents, n_edges, is_bio_prior, error (if any)
    """
    # Build request JSON
    req = {
        "goal": f"验证 {scenario} 场景（bio advantage 实验）",
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
    req_path = Path(SWARMLABS) / "agentteams" / "samples" / f"_bio_adv_{scenario}.json"
    req_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build command
    cmd = [PYTHON, str(Path(SWARMLABS) / "agentteams" / "run.py"),
           "--request", str(req_path), "--no-local-model"]
    topo_file = _topology_file(blueprint_name)
    if topo_file:
        cmd.extend(["--topology", topo_file])

    # Run
    env = os.environ.copy()
    env["FLYBRAIN_DATA_DIR"] = r"C:\Users\xing\Desktop\flybrain-connectome\male_cns"
    env["FLYBRAIN_API_KEY"] = local_api_key()
    # Bypass sandbox proxy
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env.pop(k, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"

    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=SWARMLABS, timeout=120, env=env)
    except subprocess.TimeoutExpired:
        return {"scenario": scenario, "config": blueprint_name or "baseline",
                "blueprint": blueprint_name or "baseline",
                "wall_ms": round((time.time() - t0) * 1000),
                "error": "timeout", "score": None, "converged": None,
                "n_agents": 0, "n_edges": 0, "is_bio_prior": None}

    wall_ms = round((time.time() - t0) * 1000)

    # Read latest run result
    runs_dir = Path(SWARMLABS) / "agentteams" / "runs"
    if not runs_dir.exists():
        return {"scenario": scenario, "config": blueprint_name or "baseline",
                "blueprint": blueprint_name or "baseline",
                "wall_ms": wall_ms, "error": "no runs dir",
                "score": None, "converged": None,
                "n_agents": 0, "n_edges": 0, "is_bio_prior": None}
    runs = sorted(runs_dir.iterdir())
    if not runs:
        return {"scenario": scenario, "config": blueprint_name or "baseline",
                "blueprint": blueprint_name or "baseline",
                "wall_ms": wall_ms, "error": "no run",
                "score": None, "converged": None,
                "n_agents": 0, "n_edges": 0, "is_bio_prior": None}
    latest = runs[-1]
    result_path = latest / "result.json"
    if not result_path.exists():
        return {"scenario": scenario, "config": blueprint_name or "baseline",
                "blueprint": blueprint_name or "baseline",
                "wall_ms": wall_ms, "error": "no result.json",
                "score": None, "converged": None,
                "n_agents": 0, "n_edges": 0, "is_bio_prior": None}

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"scenario": scenario, "config": blueprint_name or "baseline",
                "blueprint": blueprint_name or "baseline",
                "wall_ms": wall_ms, "error": f"parse: {e}",
                "score": None, "converged": None,
                "n_agents": 0, "n_edges": 0, "is_bio_prior": None}

    # Extract metrics from loop_report
    lr = result.get("loop_report", {})
    score = lr.get("evaluate", {}).get("team_score")
    # converged_ratio is "X/Y" string, convert to float
    conv_raw = lr.get("evaluate", {}).get("converged_ratio")
    if isinstance(conv_raw, str) and "/" in conv_raw:
        parts = conv_raw.split("/")
        try:
            converged = int(parts[0]) / int(parts[1]) if int(parts[1]) > 0 else 0.0
        except (ValueError, ZeroDivisionError):
            converged = None
    else:
        converged = conv_raw

    # Count agents and edges from topology_source (if present)
    n_agents = 0
    n_edges = 0
    is_bio_prior = None
    topo_src = lr.get("topology_source", {})
    if topo_src:
        n_agents = topo_src.get("n_agents", 0)
        n_edges = topo_src.get("n_edges", 0)
    # Fallback: count from swarm if topology_source not available
    if n_agents == 0:
        swarm = result.get("swarm", {})
        agents = swarm.get("agents", [])
        edges = swarm.get("edges", [])
        n_agents = len(agents)
        n_edges = len(edges)
    # Read is_bio_prior from the topology file itself (SwarmLabs doesn't propagate it yet)
    is_bio_prior = _read_bio_prior(blueprint_name)

    return {
        "scenario": scenario,
        "config": config_name or (blueprint_name or "baseline"),
        "blueprint": blueprint_name or "baseline",
        "wall_ms": wall_ms,
        "score": score,
        "converged": converged,
        "n_agents": n_agents,
        "n_edges": n_edges,
        "is_bio_prior": is_bio_prior,
        "error": None,
    }


def mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = mean(vals)
    return (sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-repeats", type=int, default=3, help="每个配置重复次数")
    ap.add_argument("--quick", action="store_true", help="只跑 3 场景 × 3 配置（快速验证）")
    args = ap.parse_args()

    n_rep = args.n_repeats
    scenarios = SCENARIOS_QUICK if args.quick else SCENARIOS
    configs = CONFIGS_QUICK if args.quick else CONFIGS

    total = len(scenarios) * len(configs) * n_rep
    print(f"生物学优势对照实验")
    print(f"配置: {len(scenarios)} 场景 × {len(configs)} 配置 × {n_rep} 轮 = {total} 样本")
    print(f"场景: {', '.join(scenarios)}")
    print(f"配置: {[c[0] for c in configs]}")
    print(f"预计时间: {total * 30} 秒（每次约 30s）\n")

    results: list[dict] = []

    for i, sc in enumerate(scenarios):
        print(f"[{i+1}/{len(scenarios)}] {sc}")
        for config_name, bp_name in configs:
            for rep in range(n_rep):
                tag = f"{sc} / {config_name} / rep{rep+1}"
                r = run_once(sc, bp_name, config_name=config_name)
                results.append(r)
                err = f" ERR={r.get('error')}" if r.get("error") else ""
                print(f"  {tag:45s} wall={r['wall_ms']:>5d}ms "
                      f"score={r['score']} converged={r['converged']} "
                      f"n={r['n_agents']}/{r['n_edges']} "
                      f"bio={r['is_bio_prior']}{err}")

    # 写 CSV
    out_csv = Path(__file__).parent / "e2e_bio_advantage.csv"
    fieldnames = ["scenario", "config", "blueprint", "wall_ms", "score",
                  "converged", "n_agents", "n_edges", "is_bio_prior", "error"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in fieldnames})
    print(f"\nCSV 写入: {out_csv}")

    # 统计汇总
    print(f"\n{'='*100}")
    print(f"统计汇总（{n_rep} 轮重复）")
    print(f"{'='*100}")
    print(f"{'scenario':<32s} {'config':<35s} {'wall_ms mean±std':>22s} "
          f"{'score mean±std':>18s} {'converged mean':>14s} {'bio_prior':>10s}")
    print("-" * 100)

    for sc in scenarios:
        for config_name, _ in configs:
            vals = [r for r in results
                    if r["scenario"] == sc and r["config"] == config_name
                    and not r.get("error")]
            if not vals:
                print(f"{sc:<32s} {config_name:<35s} {'(数据不足)':>22s}")
                continue
            wall_vals = [v["wall_ms"] for v in vals if v["wall_ms"] is not None]
            score_vals = [v["score"] for v in vals if v["score"] is not None]
            conv_vals = [v["converged"] for v in vals if v["converged"] is not None]
            bio_flags = [v["is_bio_prior"] for v in vals if v["is_bio_prior"] is not None]
            bio_str = "T" if any(bio_flags) else ("F" if bio_flags else "?")
            wall_str = f"{mean(wall_vals):.0f}±{std(wall_vals):.0f}" if wall_vals else "N/A"
            score_str = f"{mean(score_vals):.3f}±{std(score_vals):.3f}" if score_vals else "N/A"
            conv_str = f"{mean(conv_vals):.3f}" if conv_vals else "N/A"
            print(f"{sc:<32s} {config_name:<35s} {wall_str:>22s} "
                  f"{score_str:>18s} {conv_str:>14s} {bio_str:>10s}")
        print("-" * 100)

    # 关键对比：bio blueprint vs baseline
    print(f"\n{'='*100}")
    print("关键对比：bio blueprint vs baseline（wall_ms 差异）")
    print(f"{'='*100}")
    print(f"{'scenario':<32s} {'baseline mean':>14s} {'bio mean':>14s} "
          f"{'Δ%':>8s} {'显著?':>6s}")
    print("-" * 80)

    n_sig = 0
    for sc in scenarios:
        b_vals = [r["wall_ms"] for r in results
                  if r["scenario"] == sc and r["config"] == "baseline"
                  and not r.get("error") and r["wall_ms"] is not None]
        p_vals = [r["wall_ms"] for r in results
                  if r["scenario"] == sc and r["config"] == "competitive_selection"
                  and not r.get("error") and r["wall_ms"] is not None]
        if not b_vals or not p_vals:
            print(f"{sc:<32s} {'(数据不足)':>14s} {'(数据不足)':>14s}")
            continue
        b_mean = mean(b_vals)
        p_mean = mean(p_vals)
        delta_pct = ((p_mean - b_mean) / b_mean) * 100 if b_mean else 0
        # Simple significance: |delta| > 15% and std < 10% of mean
        b_std = std(b_vals)
        p_std = std(p_vals)
        sig = abs(delta_pct) > 15 and (b_std / b_mean < 0.1 or p_std / p_mean < 0.1)
        if sig:
            n_sig += 1
        print(f"{sc:<32s} {b_mean:>14.0f} {p_mean:>14.0f} "
              f"{delta_pct:>+7.1f}% {'YES' if sig else 'no':>6s}")

    print(f"\n显著加速: {n_sig}/{len(scenarios)} 场景")
    if n_sig == 0:
        print("结论：生物学蓝图相对 baseline 无显著性能优势。")
        print("项目定位应为：审计工具 + motif 可追溯性（架构保证），非性能工具。")
    elif n_sig < len(scenarios) / 2:
        print(f"结论：{n_sig}/{len(scenarios)} 场景显著加速，生物学优势部分成立。")
        print("建议：找出显著加速的场景类型，作为核心定位。")
    else:
        print(f"结论：{n_sig}/{len(scenarios)} 场景显著加速，生物学优势成立。")
        print("建议：可以推进商业化，核心卖点是生物学先验带来的性能优势。")

    # 生成 Markdown 报告
    report_path = Path(__file__).parent / "BIO_ADVANTAGE_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 生物学优势对照实验报告\n\n")
        f.write(f"**日期**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**配置**：{len(scenarios)} 场景 × {len(configs)} 配置 × {n_rep} 轮 = {total} 样本\n\n")
        f.write("## 实验设计\n\n")
        f.write("| 配置 | 蓝图 | 生物先验 | 说明 |\n")
        f.write("|---|---|---|---|\n")
        f.write("| baseline | 无 | 否 | 纯随机拓扑，flybrain 默认 |\n")
        f.write("| sequential | sequential | 否 | basic 蓝图，人工前馈链 |\n")
        f.write("| competitive_selection | competitive_selection | 是 | bio 蓝图，APL body 10540 |\n")
        f.write("| combo_dr_cs | deep_reasoning+competitive_selection | 是 | 组合（basic + bio） |\n\n")
        f.write(f"## 结果汇总\n\n")
        f.write(f"显著加速场景：{n_sig}/{len(scenarios)}\n\n")
        if n_sig == 0:
            f.write("**结论**：生物学蓝图相对 baseline 无显著性能优势。\n\n")
            f.write("项目定位应为：审计工具 + motif 可追溯性（架构保证），非性能工具。\n")
        else:
            f.write(f"**结论**：{n_sig}/{len(scenarios)} 场景显著加速，生物学优势部分成立。\n\n")
            f.write("建议找出显著加速的场景类型，作为核心定位。\n")
        f.write("\n## 详细数据\n\n")
        f.write("见 `e2e_bio_advantage.csv`\n")

    print(f"\n报告写入: {report_path}")


if __name__ == "__main__":
    main()
