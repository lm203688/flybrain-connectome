#!/usr/bin/env python3
"""Gate 23 — 预置堆叠蓝图（stacked blueprints）内部一致性 + 摘要自洽。

stdlib-only（只读 JSON 做结构断言，不需要 numpy），因此在 --quick 下也跑。

`male_cns/stacked_blueprints.json` 是 T5 组合代数「堆叠语义」的预置产物，被
实时 MCP 工具 `list_stacked_blueprints` / `get_stacked_feasibility` 直接读取
（server.py 懒加载，见 `_list_stacked_blueprints`）。它此前**没有任何门禁守护**，
是路线图 §七 梳理时暴露的最后一个无门禁交付物：文件若被改坏（可行性被静默
翻转、摘要与 stacks 脱节、组件数与 components 不符），CI 完全无法发现。

本门禁不信任文件自带的 `summary`，而是**独立重算** every summary 字段并与
文件声明对比；任何对 stacks 或 summary 的篡改都会被捕获。

fail-closed：在深拷贝上改坏，确认本门禁真的报红。注入与还原是**两个独立动作**
（原始 dict 从未被改过，注入只发生在副本上）—— 不要写"同一个闭包调两次"式
的 apply/restore，那在 pop/append 上会叠加而不是还原。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "male_cns" / "stacked_blueprints.json"

REQUIRED_STACK_KEYS = (
    "name", "label", "combination", "feasibility", "expected_stability",
    "rational", "use_cases", "expected_motifs",
)
REQUIRED_FEAS_KEYS = (
    "feasible", "combination", "n_components", "components", "motif_traces",
    "n_distinct_motifs", "n_motifs_matches_expected", "organism_stats",
    "metrics_snapshot", "stability_target", "expected_stability",
    "stability_in_range", "generation_ms",
)
REQUIRED_ORG_KEYS = (
    "n_nodes", "n_edges_total", "n_blueprint_edges", "blueprint_edges_added",
    "fanout_edge_count", "fanout_explosion", "fanout_edge_count_threshold",
    "rule_conflicts",
)
REQUIRED_METRIC_KEYS = (
    "n_nodes", "n_edges", "avg_degree", "inhibition_ratio",
    "intra_module_edges", "inter_module_edges", "modularity_est",
)


def audit(doc: dict) -> list[str]:
    """返回错误列表；空 = 通过。"""
    errs: list[str] = []

    if not isinstance(doc, dict):
        return ["top-level document is not an object"]
    if not doc.get("schema_version"):
        errs.append("schema_version missing")

    stacks = doc.get("stacks")
    if not isinstance(stacks, list) or not stacks:
        errs.append("stacks missing or empty")
        return errs  # 后续检查无从谈起

    n_stacks = doc.get("n_stacks")
    if n_stacks != len(stacks):
        errs.append("n_stacks=%r != len(stacks)=%d" % (n_stacks, len(stacks)))

    feasible_flags: list[bool] = []
    stability_ok_flags: list[bool] = []
    fanout_sum = 0

    for i, st in enumerate(stacks):
        where = "stacks[%d]" % i
        for k in REQUIRED_STACK_KEYS:
            if k not in st:
                errs.append("%s missing required key %r" % (where, k))

        feas = st.get("feasibility") or {}
        for k in REQUIRED_FEAS_KEYS:
            if k not in feas:
                errs.append("%s.feasibility missing required key %r" % (where, k))
        org = feas.get("organism_stats") or {}
        for k in REQUIRED_ORG_KEYS:
            if k not in org:
                errs.append("%s.feasibility.organism_stats missing %r" % (where, k))
        met = feas.get("metrics_snapshot") or {}
        for k in REQUIRED_METRIC_KEYS:
            if k not in met:
                errs.append("%s.feasibility.metrics_snapshot missing %r" % (where, k))

        # feasibility.combination 必须与顶层 combination 一致
        if feas.get("combination") != st.get("combination"):
            errs.append("%s.feasibility.combination != combination" % where)

        # n_components 必须等于 len(components)
        comps = feas.get("components") or []
        if feas.get("n_components") != len(comps):
            errs.append("%s n_components=%r != len(components)=%d"
                        % (where, feas.get("n_components"), len(comps)))

        # components 必须是 combination 按 '+' 切分后的集合
        if isinstance(st.get("combination"), str):
            parts = [p.strip() for p in st["combination"].split("+") if p.strip()]
            if sorted(parts) != sorted(comps):
                errs.append("%s components %r != split(combination) %r"
                            % (where, comps, parts))

        # 每个 stack 都必须声明 motif 数匹配 + 稳定性在范围内
        if feas.get("n_motifs_matches_expected") is not True:
            errs.append("%s n_motifs_matches_expected != true" % where)
        if feas.get("stability_in_range") is not True:
            errs.append("%s stability_in_range != true" % where)

        feasible_flags.append(bool(feas.get("feasible")))
        stability_ok_flags.append(bool(feas.get("stability_in_range")))
        try:
            fanout_sum += int(org.get("fanout_edge_count", 0))
        except (TypeError, ValueError):
            errs.append("%s fanout_edge_count not int" % where)

    # ---- summary 自洽：本门禁独立重算并与文件声明对比 --------------
    # 这是 fail-closed 的核心：summary 是文件自报的"结论"，必须由 stacks 重算得到。
    summary = doc.get("summary") or {}
    derived_all_feasible = all(feasible_flags)
    derived_all_stability = all(stability_ok_flags)
    derived_n_feasible = sum(feasible_flags)
    derived_n_stability = sum(stability_ok_flags)

    if summary.get("all_feasible") is not derived_all_feasible:
        errs.append("summary.all_feasible=%r != derived %r"
                    % (summary.get("all_feasible"), derived_all_feasible))
    if summary.get("all_stability_ok") is not derived_all_stability:
        errs.append("summary.all_stability_ok=%r != derived %r"
                    % (summary.get("all_stability_ok"), derived_all_stability))
    if summary.get("n_feasible") != derived_n_feasible:
        errs.append("summary.n_feasible=%r != derived %d"
                    % (summary.get("n_feasible"), derived_n_feasible))
    if summary.get("n_stability_ok") != derived_n_stability:
        errs.append("summary.n_stability_ok=%r != derived %d"
                    % (summary.get("n_stability_ok"), derived_n_stability))
    if summary.get("total_fanout_edges") != fanout_sum:
        errs.append("summary.total_fanout_edges=%r != derived %d"
                    % (summary.get("total_fanout_edges"), fanout_sum))
    return errs


INJECTIONS = [
    ("flip a stack.feasible to false",
     lambda d: d["stacks"][0]["feasibility"].__setitem__("feasible", False)),
    ("corrupt n_stacks count",
     lambda d: d.__setitem__("n_stacks", 99)),
    ("corrupt summary.total_fanout_edges",
     lambda d: d["summary"].__setitem__(
         "total_fanout_edges", d["summary"]["total_fanout_edges"] + 1)),
    ("drop a required top-level stack key",
     lambda d: d["stacks"][1].pop("combination")),
    ("mismatch feasibility.combination",
     lambda d: d["stacks"][2]["feasibility"].__setitem__(
         "combination", "wrong+combo")),
    ("n_components out of sync with components",
     lambda d: d["stacks"][3]["feasibility"].__setitem__("n_components", 99)),
    ("drop a feasibility key",
     lambda d: d["stacks"][4]["feasibility"].pop("stability_in_range")),
    ("desync summary.all_feasible",
     lambda d: d["summary"].__setitem__("all_feasible", False)),
]


def main() -> int:
    print("=" * 72)
    print("GATE 23 — prebuilt stacked blueprints integrity")
    print("=" * 72)

    if not ART.exists():
        print("GATE 23: FAIL -- %s not found" % ART)
        return 1
    try:
        base = json.loads(ART.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        print("GATE 23: FAIL -- %s unreadable: %r" % (ART.name, e))
        return 1

    errs = audit(base)
    if errs:
        for e in errs:
            print("  [FAIL] " + e)
        print("GATE 23: FAIL -- %d assertion(s) violated on the real artifact"
              % len(errs))
        return 1

    n_stacks = len(base.get("stacks") or [])
    print("  [ok] %d stacked blueprints, schema %s"
          % (n_stacks, base.get("schema_version")))
    print("  [ok] summary consistent: all_feasible=%s total_fanout=%s"
          % (base["summary"].get("all_feasible"),
             base["summary"].get("total_fanout_edges")))

    # ---- fail-closed injections --------------------------------------
    # 每次都在深拷贝上动手，原始 base 全程不被修改，因此还原就是"丢掉副本"，
    # 不存在 apply/restore 叠加的风险。
    print("  -- fail-closed injections --")
    broken: list[tuple[str, str]] = []
    for label, mutate in INJECTIONS:
        d = copy.deepcopy(base)
        try:
            mutate(d)
        except (KeyError, ValueError, StopIteration) as e:
            broken.append((label, "injection itself failed: %r" % e))
            continue
        got = audit(d)
        if not got:
            broken.append((label, "mutation passed undetected"))
            print("  [FAIL] injecting: %s -> NOT caught" % label)
        else:
            print("  [ok]   injecting: %s -> caught (%s)"
                  % (label, got[0][:78]))

    if broken:
        print("GATE 23: FAIL -- %d injection(s) not caught" % len(broken))
        for label, why in broken:
            print("         - %s: %s" % (label, why))
        return 1

    print("GATE 23: PASS -- %d stacks audited, %d assertions, %d injections caught"
          % (n_stacks, len(errs) + len(INJECTIONS), len(INJECTIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
