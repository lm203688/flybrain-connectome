"""
Blueprint 选择启发式：根据任务特征自动推荐最合适的蓝图（或蓝图组合）。

状态：⏸ 归档（2026-09-18 SwarmLabs 决策 Q5：暂不集成）
-----------------------------------------------
SwarmLabs 侧当前用「用户手动指定蓝图」（方式 C）：
- 理由：12 数据点样本量不足 + PlannerAgent 已有 SEMANTIC_ROUTE(29 词表) 做语义路由，不需要额外蓝图选择器
- 当前状态与 SwarmLabs 侧一致：SwarmLabs 侧也不调用本模块
- 本文件保留作「数据积累后可能的集成参考」，不主动推广

唤醒条件：SwarmLabs 收集到 20+ 场景的实测数据（当前 12 点），或明确要求「蓝图自动选择」能力。
在此之前，用户仍可用 `--blueprint <name>` 手动指定。
-----------------------------------------------

背景：Phase 4 跨域验证发现"最优蓝图与任务类型强相关"：
- 跨域桥接任务 → competitive_selection 最优 (-15.5%)
- 多步深推理 → orchestrated 最优 (-3.7%)
- 候选竞争 → deep_reasoning 最优 (-21.9%)（反直觉）
- 单场景简单任务 → baseline (无 blueprint) 就够了

本模块把上述经验规则化为启发式：输入 request JSON，输出推荐 blueprint 标签。
可单独运行做批量推荐，也可被 SwarmLabs 侧 PlannerAgent 调用。

用法：
    python blueprint_selector.py                          # 批量给所有样本推荐
    python blueprint_selector.py --request path/to.json    # 给单个 request 推荐
    python blueprint_selector.py --json                    # JSON 输出（便于机器消费）

启发式规则：
    R1. 单场景 & dim=1 & n_train<50 → baseline（无 blueprint 开销）
    R2. 多场景 & 跨域 → competitive_selection（候选竞争模式）
    R3. 多场景 & 同域 & 参数多 → deep_reasoning（记忆回环）
    R4. 场景名含 compete/haldane/quorum/antibiotic → competitive_selection
    R5. 场景名含 fedbatch/chemostat/fba/lifecycle → orchestrated（长时任务）
    R6. 场景名含 surrogate/doe/sobol/mle → orchestrated（拟合/采样任务）
    R7. 场景名含 uq/cal → orchestrated（不确定量化需要全局仲裁）
    R8. 高维 (dim>=3) → deep_reasoning+orchestrated（组合：强推理+强协调）
    R9. 2D & 多场景 & noise → deep_reasoning（2D 记忆回环价值大）
    R10. 默认（无法判断）→ deep_reasoning
"""
import argparse
import json
import sys
from pathlib import Path

SWARMLABS = r"C:\Users\xing\Desktop\swarmlabs"


def load_scenario_catalog():
    """从 SwarmLabs 的 scenario catalog 加载元数据（key → 元信息）"""
    sys.path.insert(0, SWARMLABS)
    import os
    old_cwd = os.getcwd()
    os.chdir(SWARMLABS)
    try:
        from agentteams.skills._engine import _all_scenarios
        scenarios = _all_scenarios(None)
    finally:
        os.chdir(old_cwd)

    catalog = {}
    for s in scenarios:
        catalog[s["key"]] = {
            "category": s.get("category", "unknown"),
            "domain": s.get("domain", ""),
            "dim": len(s.get("bounds", [])),
            "n_train": s.get("n_train", 0),
            "noise": s.get("noise", 0),
        }
    return catalog


def score_blueprint(features: dict) -> dict:
    """
    根据任务特征打分，返回所有蓝图的得分 + 推荐。

    features 需包含：
        n_scenarios, scenarios (list), top_n, features (场景元信息 dict)

    返回：
        {
            "recommendation": "deep_reasoning" | "orchestrated" | ... ,
            "scores": {"deep_reasoning": 3, "orchestrated": 2, ...},
            "reasons": ["R4: 场景含 compete 关键词", ...],
            "confidence": 0.0-1.0
        }
    """
    scenarios = features.get("scenarios", [])
    n_scenarios = features.get("n_scenarios", len(scenarios))
    top_n = features.get("top_n", 0)
    meta = features.get("features", {})  # {scenario_key: {category, dim, noise, ...}}

    # 聚合特征
    all_dims = [meta[k].get("dim", 1) for k in scenarios if k in meta]
    all_noise = [meta[k].get("noise", 0) for k in scenarios if k in meta]
    all_cats = set(meta[k].get("category", "unknown") for k in scenarios if k in meta)
    max_dim = max(all_dims) if all_dims else 1
    any_noisy = any(n > 0 for n in all_noise)

    # 关键词扫描
    keys_lower = " ".join(scenarios).lower()
    compete_kw = any(k in keys_lower for k in ["compet", "haldane", "quorum", "antibiotic"])
    longrun_kw = any(k in keys_lower for k in ["fedbatch", "chemostat", "lifecycle", "fba", "biofilm"])
    fit_kw = any(k in keys_lower for k in ["surrogate", "doe", "sobol", "mle"])
    uq_kw = any(k in keys_lower for k in ["uq", "cal"])

    # 打分（0-10）
    scores = {
        "baseline": 2,          # 保守默认：无 blueprint（单场景用这个就够了）
        "deep_reasoning": 4,    # 通用最强：记忆回环对多步任务价值最大
        "orchestrated": 3,
        "competitive_selection": 3,
        "fast_reflex": 1,       # 实时反射，科研任务几乎不用
        "broad_explore": 2,
        "hierarchical": 2,
        "lateral_inhibition": 2,
        "predictive_coding": 2,
    }
    reasons = []

    # R0: 无场景列表（如 request_auto）→ 用通用最强 deep_reasoning
    if not scenarios:
        scores["deep_reasoning"] += 4
        reasons.append("R0: 无指定场景（auto 模式）→ deep_reasoning 通用最强")

    # R1: 单场景 + 简单 → baseline
    if n_scenarios == 1 and max_dim == 1 and all(meta[k].get("n_train", 0) < 50 for k in scenarios if k in meta):
        scores["baseline"] += 5
        reasons.append("R1: 单场景 + 简单参数 → baseline（零 blueprint 开销）")

    # R2: 多场景 + 跨域 → competitive_selection
    if n_scenarios >= 3 and len(all_cats) >= 2:
        scores["competitive_selection"] += 4
        scores["broad_explore"] += 2
        reasons.append(f"R2: 多场景({n_scenarios}) + 跨域({len(all_cats)}域) → competitive_selection")

    # R3: 多场景 + 同域 + 多参数 → deep_reasoning
    if n_scenarios >= 3 and len(all_cats) == 1 and max_dim >= 2:
        scores["deep_reasoning"] += 4
        reasons.append(f"R3: 多场景({n_scenarios}) + 同域 + dim>1 → deep_reasoning")

    # R3b: 多场景 + 生物学（复杂动力学）→ deep_reasoning
    # 实证：Phase 4 中 compete 任务（3 微生物竞争场景）deep_reasoning 最优 (-21.9%)
    if n_scenarios >= 3 and "biology" in all_cats:
        scores["deep_reasoning"] += 3
        reasons.append(f"R3b: 多场景({n_scenarios}) + 生物学 → deep_reasoning（复杂动力学）")

    # R4: 竞争关键词 → competitive_selection（弱权重，避免名称误导）
    if compete_kw:
        scores["competitive_selection"] += 2
        reasons.append("R4: 场景名含竞争关键词 → competitive_selection（弱权重）")

    # R5: 长时任务关键词 → orchestrated
    if longrun_kw:
        scores["orchestrated"] += 3
        reasons.append("R5: 场景名含长时任务关键词 → orchestrated")

    # R6: 拟合/采样关键词 → orchestrated
    if fit_kw:
        scores["orchestrated"] += 3
        scores["broad_explore"] += 1
        reasons.append("R6: 场景名含拟合/采样关键词 → orchestrated")

    # R7: UQ/校准关键词 → orchestrated
    if uq_kw:
        scores["orchestrated"] += 2
        reasons.append("R7: 场景名含 UQ/校准关键词 → orchestrated")

    # R8: 高维 → deep_reasoning + orchestrated 组合
    if max_dim >= 3:
        scores["deep_reasoning"] += 2
        scores["orchestrated"] += 2
        reasons.append(f"R8: 高维(dim={max_dim}) → deep_reasoning+orchestrated")

    # R9: 2D + 多场景 + noisy → deep_reasoning
    if max_dim == 2 and n_scenarios >= 2 and any_noisy:
        scores["deep_reasoning"] += 2
        reasons.append("R9: 2D + 多场景 + noisy → deep_reasoning")

    # R10: top_n 大 → broad_explore（更多候选并行）
    if top_n and top_n >= 5:
        scores["broad_explore"] += 1
        reasons.append(f"R10: top_n={top_n} → broad_explore 加权")

    # 计算推荐
    # 组合检测：如果两个分数接近，推荐组合
    top_scores = sorted(scores.items(), key=lambda x: -x[1])
    rec = top_scores[0][0]
    confidence = top_scores[0][1] - (top_scores[1][1] if len(top_scores) > 1 else 0)

    # 组合逻辑：如果第一名和第二名的分差 < 2，且两个都 > 3，推荐组合
    # 但 baseline 是"无蓝图"标记，不能与其他蓝图组合
    if len(top_scores) >= 2:
        top1_name, top1_score = top_scores[0]
        top2_name, top2_score = top_scores[1]
        if top1_name != "baseline" and top1_score >= 5 and top2_score >= 4 and (top1_score - top2_score) < 2:
            rec = f"{top1_name}+{top2_name}"
            top3_score = top_scores[2][1] if len(top_scores) > 2 else top1_score - 2
            confidence = top1_score - top3_score
            reasons.append(f"组合推荐: {rec} (分差<2 且都>3)")

    return {
        "recommendation": rec,
        "scores": scores,
        "reasons": reasons,
        "confidence": confidence,
    }


def recommend(request: dict, catalog: dict) -> dict:
    """主入口：接收 request JSON + scenario catalog，返回推荐"""
    scenarios = request.get("scenarios", [])
    n_scenarios = request.get("max_scenarios", len(scenarios))
    top_n = request.get("top_n", 0)

    features = {
        "scenarios": scenarios,
        "n_scenarios": n_scenarios,
        "top_n": top_n,
        "features": {k: catalog[k] for k in scenarios if k in catalog},
    }
    return score_blueprint(features)


def main():
    ap = argparse.ArgumentParser(description="Blueprint 选择启发式")
    ap.add_argument("--request", help="单个 request JSON 路径")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--all-samples", action="store_true",
                    help="扫描 SwarmLabs agentteams/samples/ 下所有 JSON 样本")
    args = ap.parse_args()

    catalog = load_scenario_catalog()

    if args.request:
        req = json.loads(Path(args.request).read_text(encoding="utf-8"))
        result = recommend(req, catalog)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"推荐 blueprint: {result['recommendation']}")
            print(f"置信度: {result['confidence']}")
            print(f"理由:")
            for r in result["reasons"]:
                print(f"  · {r}")
            print(f"得分:")
            for name, score in sorted(result["scores"].items(), key=lambda x: -x[1]):
                print(f"  {name:28s} {score}")
        return

    if args.all_samples:
        samples_dir = Path(SWARMLABS) / "agentteams" / "samples"
        files = sorted(samples_dir.glob("*.json"))
        results = []
        for f in files:
            try:
                req = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            result = recommend(req, catalog)
            results.append((f.name, req.get("scenarios", []), result))

        if args.json:
            print(json.dumps({
                "samples": [
                    {"file": n, "scenarios": s, "recommendation": r["recommendation"],
                     "confidence": r["confidence"], "reasons": r["reasons"]}
                    for n, s, r in results
                ]
            }, ensure_ascii=False, indent=2))
        else:
            print(f"{'file':<45s} {'recommendation':<30s} {'conf':>5s}")
            print("-" * 85)
            for name, sc, r in results:
                rec = r["recommendation"][:28]
                conf = r["confidence"]
                print(f"{name:<45s} {rec:<30s} {conf:>5d}")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
