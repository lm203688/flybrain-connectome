#!/usr/bin/env python3
"""
diagnostic_meta_analyzer.py — 元分析器：跨 4 个实验结果 JSON 汇总所有对比。

用途
----
从 v2.10.0 → v2.13.0 的 4 个结果 JSON 中提取 (comparison, metric, p, d, n_seeds,
verdict)，归一到统一 schema，供 CLAIMS_LEDGER.md 引用与机器审计。

判定标准（与 SIGNIFICANCE_REPORT 一致）：
  real_gain / real_loss     p<0.05 且 |d|>=0.5
  trend_gain / trend_loss   p>=0.05 且 |d|>=0.2
  no_effect                 其它
  indistinguishable         |d|<0.1 且 p>0.3（保留 significance JSON 的原始 verdict）

多重比较：对每个（实验，metric）分组做 Bonferroni 校正，输出
  bonferroni_alpha = 0.05 / 该组对比数
  survives_bonferroni     = p < bonferroni_alpha 且 |d|>=0.5

不重跑实验：完全读取现有 JSON，秒级完成。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

SOURCES = [
    {
        "version": "2.10.0",
        "file": "significance_results.json",
        "kind": "significance",
        "experiment": "multi_unit_significance",
    },
    {
        "version": "2.11.0",
        "file": "connectivity_topology_results.json",
        "kind": "ranking",  # v2.11.0 无 p/d，仅输出排序供参考
        "experiment": "connectivity_topology_efficiency",
    },
    {
        "version": "2.12.0",
        "file": "topology_capacity_results.json",
        "kind": "comparisons",
        "experiment": "topology_capacity",
    },
    {
        "version": "2.13.0",
        "file": "tree_fanout_variants_results.json",
        "kind": "comparisons",
        "experiment": "tree_fanout_variants",
    },
]

REAL_P, REAL_D = 0.05, 0.5
TREND_D = 0.2
INDIST_P, INDIST_D = 0.3, 0.1


def _classify(p, d_effect):
    """d_effect 已按"a 更好为正方向"归一化。按 SIGNIFICANCE_REPORT 判定标准分类。"""
    if p is None or d_effect is None:
        return "no_stats"
    abs_d = abs(d_effect)
    if abs_d < INDIST_D and p > INDIST_P:
        return "indistinguishable"
    if p < REAL_P and abs_d >= REAL_D:
        return "real_gain" if d_effect > 0 else "real_loss"
    if abs_d >= TREND_D:
        return "trend_gain" if d_effect > 0 else "trend_loss"
    return "no_effect"


def _row(version, experiment, metric, a, b, mean_a, mean_b, p, d, n_seeds, higher_better=True):
    """d_effect: a 相对 b 的"更好"方向效应量。

    - higher_better=True（准确率等）：d_effect = d（a 均值更大 → 正）
    - higher_better=False（MSE/latency 等）：d_effect = -d（a 均值更小 → 正）
    """
    d_effect = d if (d is None or higher_better) else -d
    verdict = _classify(p, d_effect)
    return {
        "version": version,
        "experiment": experiment,
        "metric": metric,
        "a": a,
        "b": b,
        "mean_a": round(mean_a, 6) if mean_a is not None else None,
        "mean_b": round(mean_b, 6) if mean_b is not None else None,
        "welch_p": round(p, 6) if p is not None else None,
        "cohens_d": round(d, 4) if d is not None else None,
        "d_effect": round(d_effect, 4) if d_effect is not None else None,
        "n_seeds": n_seeds,
        "higher_better": higher_better,
        "verdict": verdict,
    }


def load_significance():
    src = HERE / "significance_results.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    n_seeds = d["n_seeds"]
    rows = []
    for c in d["comparisons"]:
        # higher_better=True → 越大越好（parity/logistic）；
        # narma10/large_mse 类指标 lower_better，把 d 取反后分类
        hb = bool(c.get("higher_better", True))
        rows.append(_row(
            version="2.10.0",
            experiment="multi_unit_significance",
            metric=c["task"],
            a=c["arm"],
            b="bio_motif",
            mean_a=c["cand_mean"],
            mean_b=c["bio_mean"],
            p=c.get("welch_p"),
            d=c.get("cohens_d"),
            n_seeds=n_seeds,
            higher_better=hb,
        ))
    return rows


def load_topology_capacity():
    src = HERE / "topology_capacity_results.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    # n_seeds_per_metric = 5, n_seeds_narma10 = 5
    n_seeds_by_metric = {}
    for r in d.get("compositions_measured", []):
        # 从 raw 数据推不出 per-metric n_seeds；保守用较小值
        pass
    # v2.12.0 用 n_seeds=5（quick）+ n_seeds=10（final）——取较大值 10
    # 从 comparisons_new_vs_chained 里读
    n_seeds = d.get("n_seeds_per_metric") or d.get("n_seeds_narma10") or 5
    rows = []
    for c in d.get("comparisons_new_vs_chained", []):
        metric = c.get("metric") or ""
        # narma10 是 MSE（越低越好），其它是 memory/latency（越大越好）
        hb = metric != "narma10"
        rows.append(_row(
            version="2.12.0",
            experiment="topology_capacity",
            metric=metric,
            a=c.get("new"),
            b=c.get("chained"),
            mean_a=c.get("mean_a"),
            mean_b=c.get("mean_b"),
            p=c.get("p"),
            d=c.get("d"),
            n_seeds=n_seeds,
            higher_better=hb,
        ))
    return rows


def load_tree_fanout():
    src = HERE / "tree_fanout_variants_results.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    n_seeds = d.get("n_seeds", 10)
    rows = []
    for c in d.get("comparisons_vs_ref", []):
        metric = c.get("metric") or ""
        hb = metric != "narma10"
        rows.append(_row(
            version="2.13.0",
            experiment="tree_fanout_variants",
            metric=metric,
            a=c.get("variant"),
            b=c.get("reference"),
            mean_a=c.get("mean_a"),
            mean_b=c.get("mean_b"),
            p=c.get("p"),
            d=c.get("d"),
            n_seeds=n_seeds,
            higher_better=hb,
        ))
    return rows


def load_connectivity_topology_ranking():
    """v2.11.0 无 per-seed 数据 → 只输出 ranking 供人工审计，不做 verdict。"""
    src = HERE / "connectivity_topology_results.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    rows = []
    for r in d.get("ranking", []):
        rows.append({
            "version": "2.11.0",
            "experiment": "connectivity_topology_efficiency",
            "metric": "narma10_mse",
            "a": r["label"],
            "b": None,
            "mean_a": round(r.get("narma10_mse", float("nan")), 6),
            "mean_b": None,
            "welch_p": None,
            "cohens_d": None,
            "n_seeds": d.get("n_seeds"),
            "higher_better": False,
            "verdict": "ranking_only",
            "direction": "lower_better",
        })
    return rows


def bonferroni_pass(rows, group_by=("experiment", "metric")):
    """按组做 Bonferroni 校正，加 survives_bonferroni 字段。"""
    groups: dict = {}
    for r in rows:
        key = tuple(r.get(k) for k in group_by)
        groups.setdefault(key, []).append(r)
    for key, members in groups.items():
        n = len(members)
        alpha = 0.05 / max(n, 1)
        for m in members:
            m["bonferroni_alpha"] = round(alpha, 6)
            p, d = m.get("welch_p"), m.get("cohens_d")
            if p is None or d is None:
                m["survives_bonferroni"] = False
                continue
            # 使用 d_effect（已归一到"a 更好为正"方向）
            de = m.get("d_effect")
            if de is None:
                m["survives_bonferroni"] = False
            else:
                m["survives_bonferroni"] = bool(p < alpha and abs(de) >= REAL_D)
    return rows


def main():
    all_rows = []
    for src in SOURCES:
        if src["kind"] == "significance":
            all_rows.extend(load_significance())
        elif src["kind"] == "comparisons":
            if "capacity" in src["experiment"]:
                all_rows.extend(load_topology_capacity())
            else:
                all_rows.extend(load_tree_fanout())
        elif src["kind"] == "ranking":
            all_rows.extend(load_connectivity_topology_ranking())

    # Bonferroni 只对有 p/d 的对比做校正
    bonf_rows = [r for r in all_rows if r.get("welch_p") is not None]
    bonferroni_pass(bonf_rows)

    # 汇总统计
    def count(pred):
        return sum(1 for r in all_rows if pred(r))

    summary = {
        "total_rows": len(all_rows),
        "with_stats": len(bonf_rows),
        "ranking_only": count(lambda r: r["verdict"] == "ranking_only"),
        "verdict_counts": {
            "real_gain": count(lambda r: r["verdict"] == "real_gain"),
            "real_loss": count(lambda r: r["verdict"] == "real_loss"),
            "trend_gain": count(lambda r: r["verdict"] == "trend_gain"),
            "trend_loss": count(lambda r: r["verdict"] == "trend_loss"),
            "no_effect": count(lambda r: r["verdict"] == "no_effect"),
            "indistinguishable": count(lambda r: r["verdict"] == "indistinguishable"),
            "no_stats": count(lambda r: r["verdict"] == "no_stats"),
        },
        "bonferroni_survivors": count(lambda r: r.get("survives_bonferroni")),
        "by_version": {
            v: count(lambda r, v=v: r["version"] == v)
            for v in ["2.10.0", "2.11.0", "2.12.0", "2.13.0"]
        },
        # 关键诚实性检查：每个实验的 n_seeds 实际取值
        "n_seeds_per_experiment": {},
        # n_seeds<10 的"real_gain" 应视为样本偏差候选
        "weak_n_real_gains": count(lambda r: r["verdict"] == "real_gain" and (r["n_seeds"] or 0) < 10),
    }
    for r in all_rows:
        key = f"{r['version']}_{r['experiment']}"
        summary["n_seeds_per_experiment"].setdefault(key, set()).add(r.get("n_seeds"))
    # set → sorted list for JSON
    summary["n_seeds_per_experiment"] = {
        k: sorted(v, key=lambda x: (x is None, x))
        for k, v in summary["n_seeds_per_experiment"].items()
    }

    out = {
        "schema": "claims_ledger_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "criteria": {
            "real": {"p": f"<{REAL_P}", "|d|": f">={REAL_D}"},
            "trend": {"p": f">={REAL_P}", "|d|": f">={TREND_D}"},
            "indistinguishable": {"p": f">{INDIST_P}", "|d|": f"<{INDIST_D}"},
        },
        "summary": summary,
        "rows": all_rows,
    }

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        out_path = Path(sys.argv[1])
    else:
        out_path = HERE / "claims_audit.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote: {out_path}")
    print(f"Total rows: {summary['total_rows']}  with_stats: {summary['with_stats']}")
    print(f"Verdicts: {summary['verdict_counts']}")
    print(f"Bonferroni survivors: {summary['bonferroni_survivors']}")
    print(f"Weak-n (n_seeds<10) real_gains: {summary['weak_n_real_gains']}")
    print(f"By version: {summary['by_version']}")
    print(f"n_seeds per experiment: {summary['n_seeds_per_experiment']}")
    print()
    print("Real_gain rows:")
    for r in all_rows:
        if r["verdict"] == "real_gain":
            sb = "✅" if r.get("survives_bonferroni") else "❌"
            print(f"  {sb} {r['version']} {r['experiment']} {r['metric']}")
            print(f"     {r['a']} vs {r['b']}  mean={r['mean_a']} vs {r['mean_b']}  p={r['welch_p']}  d={r['cohens_d']}  n={r['n_seeds']}")
    print()
    print("Real_loss rows:")
    for r in all_rows:
        if r["verdict"] == "real_loss":
            sb = "✅" if r.get("survives_bonferroni") else "❌"
            print(f"  {sb} {r['version']} {r['experiment']} {r['metric']}")
            print(f"     {r['a']} vs {r['b']}  mean={r['mean_a']} vs {r['mean_b']}  p={r['welch_p']}  d={r['cohens_d']}  n={r['n_seeds']}")


if __name__ == "__main__":
    main()
