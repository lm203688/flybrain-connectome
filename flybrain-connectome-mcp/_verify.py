"""
_verify.py — 果蝇项目端到端冒烟测试（自包含，路径相对本文件）

覆盖：数据 → 查询层 → motif → 客户端 → 拓扑 → SwarmLabs config → 锚点数字。

跑法：
    C:\\Users\\xing\\.workbuddy\\binaries\\python\\envs\\minimind\\Scripts\\python.exe _verify.py

退出码 0 = 全过；1 = 有失败。只需 numpy + pyarrow（minimind venv 已含），
不需要起 HTTP 服务（离线路径）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "mcp_connectome"))
sys.path.insert(0, str(HERE / "motifs"))

RESULTS: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((label, bool(ok), detail))
    print("  %-46s %s  %s" % (label, "PASS" if ok else "FAIL", detail))
    return bool(ok)


def cross_module_edge_ratio(org: dict, n_modules: int) -> float:
    """Fraction of edges that span across different modules.

    v1.2.0 stability metric: an edge is "cross-module" if its from/to
    endpoints belong to different modules. Returns 0..1.
    Blueprint-design invariant: cross_module_edge_ratio <= stability_target.
    Lower values = stronger module-level isolation = better fault containment.

    Node structure (C1): {'id': 'm0_rep', 'role': 'tissue_rep', 'module': 0, ...}
    Edge structure: {'from': 'm0_rep', 'to': 'm0_rep', ..., 'module': 0}
    The 'module' field on an edge is the source module (may be same as target
    for intra-module edges, or absent for cross-module edges).
    """
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    if not edges:
        return 0.0
    node_to_mod: dict[str, int] = {}
    for nd in nodes:
        nid = nd.get("id") or nd.get("name")
        mod = nd.get("module", nd.get("module_id", 0))
        if nid:
            node_to_mod[nid] = mod
    cross = 0
    for e in edges:
        f = e.get("from")
        t = e.get("to")
        fm = node_to_mod.get(f)
        tm = node_to_mod.get(t)
        if fm is not None and tm is not None and fm != tm:
            cross += 1
    return round(cross / len(edges), 4)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="flybrain-connectome smoke test")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args(argv)

    if args.data_dir:
        os.environ["FLYBRAIN_DATA_DIR"] = args.data_dir
    elif not os.environ.get("FLYBRAIN_DATA_DIR"):
        os.environ["FLYBRAIN_DATA_DIR"] = str(HERE.parent / "male_cns")

    print("\nflybrain-connectome 端到端冒烟测试")
    print("  FLYBRAIN_DATA_DIR = %s\n" % os.environ["FLYBRAIN_DATA_DIR"])

    # ---- 1. 数据 + 查询层 ----------------------------------------- #
    import core
    core.ensure_cache(False)

    ov = core.connectome_overview()
    check("数据集总突触 = 124,177,617",
          ov["total_synapses"] == 124177617, str(ov["total_synapses"]))
    # 注意两个口径不同：ann 表 211,577 行（含胶质/碎片/未命名）；
    # 真神经元子图 = superclass 非空 = 166,700
    check("标注表行数 = 211,577",
          ov["annotated_neurons"] == 211577, str(ov["annotated_neurons"]))
    n_neuron = len(core._STATE["ann_ids"])
    check("真神经元子图（superclass 非空）= 166,700",
          n_neuron == 166700, str(n_neuron))

    pair = core.pair_synapses(10540, 12569)
    check("APL(10540) → DPM(12569) = 711 突触", pair == 711, str(pair))

    fo, fi = core.degree(10540)
    check("APL degree = (102263, 119935)", (fo, fi) == (102263, 119935),
          "fo=%d fi=%d" % (fo, fi))

    # ---- 2. motif 快照 -------------------------------------------- #
    from flybrain_connectome_client import build_agent_topology, FlybrainHTTPClient
    motif_doc = json.loads(
        (HERE / "motifs" / "swarm_agent_topology_motifs.json").read_text(encoding="utf-8"))
    check("motif 文档含三个 motif",
          set(motif_doc["motifs"]) == {"inhibitory_hub", "reservoir_smallworld",
                                       "recurrent_feedback"},
          str(sorted(motif_doc["motifs"])))
    check("motif 锚点 fanout 101-1000 = 49.36%",
          motif_doc["motifs"]["reservoir_smallworld"]
                   ["fanout_distribution_pct"]["101-1000"] == 49.36)
    check("motif 锚点 ol_intrinsic 自循环 = 28.74%",
          motif_doc["motifs"]["recurrent_feedback"]
                   ["self_recurrence_top"][0]["pct_of_total"] == 28.74)

    # ---- 3. 拓扑构建 ---------------------------------------------- #
    expected = {"inhibitory_hub": (11, 10), "reservoir_smallworld": (10, 20),
                "recurrent_feedback": (8, 8)}
    for name, mot in motif_doc["motifs"].items():
        t = build_agent_topology(mot, K_workers=10)
        n, e = len(t["nodes"]), len(t["edges"])
        check("build_agent_topology(%s) = %s" % (name, expected[name]),
              (n, e) == expected[name], "nodes=%d edges=%d" % (n, e))

    # ---- 4. C1：motif 解析（离线）+ SwarmLabs config ---------------- #
    import synthetic_bio_topology as c1
    doc, prov = c1.resolve_motifs(source="local", verbose=False)
    check("C1 resolve_motifs(local) 成功", prov["mode"] == "local_snapshot",
          prov["mode"])

    org = c1.design_organism({"n_modules": 4, "agents_per_module": 6,
                              "recurrent_pct": 0.287,
                              "module_profiles": "uniform"}, motifs=doc, seed=7)
    org["motif_provenance"] = prov
    m = org["metrics"]
    check("C1 样例 organism (uniform) = 29 节点 / 18 边",
          (m["n_nodes"], m["n_edges"]) == (29, 18),
          "nodes=%d edges=%d" % (m["n_nodes"], m["n_edges"]))

    # ---- cycled profiles (functional specialization) ----
    org_c = c1.design_organism({"n_modules": 4, "agents_per_module": 6,
                                "recurrent_pct": 0.287,
                                "module_profiles": "cycled"}, motifs=doc, seed=7)
    mc = org_c["metrics"]
    check("C1 cycled profiles: 29 节点, 边 > 16 (功能分化)",
          mc["n_nodes"] == 29 and mc["n_edges"] > 16,
          "nodes=%d edges=%d" % (mc["n_nodes"], mc["n_edges"]))
    profiles = mc.get("profile_breakdown", {})
    check("C1 cycled profiles: 4 种功能分区",
          len([k for k in profiles if k not in ("uniform",)]) >= 3,
          "profiles=%s" % list(profiles.keys()))
    cfg_c = c1.build_swarmlabs_config(org_c, name="smoke_cycled", provenance=prov)
    vc = cfg_c["swarm"]["validation"]
    check("C1 cycled swarmlabs ok", vc["ok"] is True,
          "agents=%d edges=%d ok=%s" % (vc["n_agents"], vc["n_edges"], vc["ok"]))

    # --- Phase 3: blueprint (cross-module topology, dimension 3) ---
    # 9 blueprints total: 5 basic + 4 biological
    check("MODULE_PROFILES 10 种功能模块（Phase 1 决策 1：激进 4→10）",
          len(c1.MODULE_PROFILES) == 10,
          "modules=%d" % len(c1.MODULE_PROFILES))
    check("DEFAULT_PROFILE_CYCLE 覆盖全部 10 模块",
          len(c1.DEFAULT_PROFILE_CYCLE) == 10
          and set(c1.DEFAULT_PROFILE_CYCLE) == set(c1.MODULE_PROFILES.keys()),
          "cycle=%d" % len(c1.DEFAULT_PROFILE_CYCLE))
    bp_names = list(c1.BLUEPRINTS.keys())
    basic = [k for k, v in c1.BLUEPRINTS.items() if v.get("category") == "basic"]
    bio = [k for k, v in c1.BLUEPRINTS.items() if v.get("category") == "biological"]
    synth = [k for k, v in c1.BLUEPRINTS.items() if v.get("category") == "synthetic"]
    check("BLUEPRINTS 25 种预设存在 (5 basic + 16 bio + 4 synthetic)",
          len(bp_names) == 25 and len(basic) == 5 and len(bio) == 16 and len(synth) == 4,
          "basic=%s bio=%s synth=%s" % (sorted(basic), sorted(bio), sorted(synth)))

    # Phase 2: every blueprint must trace to a motif (real or "none") — no "unknown"
    missing_prov = [k for k in bp_names if k not in c1.BLUEPRINT_SOURCE_MOTIF]
    prov_all = c1._motif_provenance({"blueprint": "+".join(bp_names)})
    unknown = [k for k, v in prov_all["blueprint_to_motif"].items()
               if v.get("source_motif") == "unknown"]
    check("全部蓝图均有 motif 追溯（无 unknown / 无遗漏）",
          not missing_prov and not unknown,
          "missing=%s unknown=%s" % (missing_prov, unknown))

    # Phase 2: synthetic blueprints are honestly marked non-bio-prior
    prov_synth = c1._motif_provenance({"blueprint": "rl_actor_critic"})
    entry_synth = prov_synth["blueprint_to_motif"].get("rl_actor_critic", {})
    check("合成蓝图 motif='none'（诚实标记非生物先验）",
          entry_synth.get("source_motif") == "none"
          and entry_synth.get("is_bio_prior") is False,
          "entry=%s" % entry_synth)

    # deep_reasoning should produce more cross edges than sequential
    org_seq = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                  "module_profiles": "cycled",
                                  "blueprint": "sequential"}, motifs=doc, seed=7)
    org_dr = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                 "module_profiles": "cycled",
                                 "blueprint": "deep_reasoning"}, motifs=doc, seed=7)
    n_seq_bp = sum(1 for e in org_seq["organism"]["edges"] if e.get("blueprint"))
    n_dr_bp = sum(1 for e in org_dr["organism"]["edges"] if e.get("blueprint"))
    check("blueprint 边正确生成",
          n_seq_bp == 3 and n_dr_bp == 2,
          "sequential=%d deep_reasoning=%d" % (n_seq_bp, n_dr_bp))

    # blueprint field propagates to SwarmLabs config
    cfg_dr = c1.build_swarmlabs_config(org_dr, name="bp_smoke", provenance=prov)
    check("swarm.json blueprint 字段存在", cfg_dr.get("blueprint") == "deep_reasoning",
          "blueprint=%s" % cfg_dr.get("blueprint"))
    bp_edges = [e for e in cfg_dr["swarm"]["edges"] if e.get("blueprint")]
    check("swarm.json blueprint 边标记全量",
          all(e.get("blueprint") == "deep_reasoning" for e in bp_edges) and len(bp_edges) == 2,
          "bp_edges=%d" % len(bp_edges))

    # blueprint=none (disabled) should produce 0 blueprint edges
    org_no = c1.design_organism({"n_modules": 4, "agents_per_module": 6,
                                 "module_profiles": "cycled",
                                 "blueprint": None}, motifs=doc, seed=7)
    n_no = sum(1 for e in org_no["organism"]["edges"] if e.get("blueprint"))
    check("blueprint=none 时 0 蓝图边", n_no == 0, "edges=%d" % n_no)

    # --- Phase 4: blueprint composition (stackable blocks) ---
    # Composition via '+' or ',' separator should dedup on (from,to,kind,semantic)
    org_a = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                "module_profiles": "cycled",
                                "blueprint": "deep_reasoning"}, motifs=doc, seed=7)
    org_b = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                "module_profiles": "cycled",
                                "blueprint": "fast_reflex"}, motifs=doc, seed=7)
    org_combo = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                    "module_profiles": "cycled",
                                    "blueprint": "deep_reasoning+fast_reflex"},
                                   motifs=doc, seed=7)
    n_a = sum(1 for e in org_a["organism"]["edges"] if e.get("blueprint"))
    n_b = sum(1 for e in org_b["organism"]["edges"] if e.get("blueprint"))
    n_combo = sum(1 for e in org_combo["organism"]["edges"] if e.get("blueprint"))
    # composition is set-union: max(a,b) <= a+b <= a+b (dedup can only reduce, never add)
    check("blueprint 组合可堆叠（max<=combo<=a+b）",
          max(n_a, n_b) <= n_combo <= n_a + n_b,
          "a=%d b=%d combo=%d" % (n_a, n_b, n_combo))
    check("blueprint 组合标签正确",
          org_combo.get("blueprint") == "deep_reasoning+fast_reflex",
          "blueprint=%s" % org_combo.get("blueprint"))

    # composed blueprint propagates to swarm.json info
    cfg_combo = c1.build_swarmlabs_config(org_combo, name="bp_smoke_combo", provenance=prov)
    info = cfg_combo.get("blueprint_info")
    check("blueprint_info 支持组合结构",
          info is not None and info.get("is_composed") is True and info.get("n_components") == 2,
          "info=%s" % info)

    # ',' separator should behave identically to '+'
    org_combo2 = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                     "module_profiles": "cycled",
                                     "blueprint": "deep_reasoning,fast_reflex"},
                                    motifs=doc, seed=7)
    n_combo2 = sum(1 for e in org_combo2["organism"]["edges"] if e.get("blueprint"))
    check("blueprint 组合：'+' 与 ',' 语义等价",
          n_combo == n_combo2, "plus=%d comma=%d" % (n_combo, n_combo2))

    # dedup test: a blueprint composed with itself should NOT double edges
    org_dup = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                  "module_profiles": "cycled",
                                  "blueprint": "deep_reasoning+deep_reasoning"},
                                 motifs=doc, seed=7)
    n_dup = sum(1 for e in org_dup["organism"]["edges"] if e.get("blueprint"))
    check("blueprint 组合去重（a+a == a）",
          n_dup == n_a, "a=%d a+a=%d" % (n_a, n_dup))

    # Phase 2: nested composition "a+(b+c)" is isomorphic to flat "a+b+c"
    # (composition is an order-independent union of cross-edge rules)
    org_nest = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                   "module_profiles": "cycled",
                                   "blueprint": "deep_reasoning+(fast_reflex+orchestrated)"},
                                  motifs=doc, seed=7)
    org_flat = c1.design_organism({"n_modules": 6, "agents_per_module": 6,
                                   "module_profiles": "cycled",
                                   "blueprint": "deep_reasoning+fast_reflex+orchestrated"},
                                  motifs=doc, seed=7)
    n_nest = sum(1 for e in org_nest["organism"]["edges"] if e.get("blueprint"))
    n_flat = sum(1 for e in org_flat["organism"]["edges"] if e.get("blueprint"))
    check("嵌套组合 a+(b+c) == 平铺 a+b+c（同构，边数一致）",
          n_nest == n_flat and n_nest > 0,
          "nested=%d flat=%d" % (n_nest, n_flat))

    # ---- schema v1.1.1: motif_provenance (blueprint → real motif → real neuron) ----
    prov_c = cfg_dr.get("motif_provenance")
    check("motif_provenance 存在（有 blueprint 时）",
          prov_c is not None and prov_c.get("blueprints_used"),
          "prov=%s" % (prov_c.get("blueprints_used") if prov_c else None))
    # dataset anchor must match MaleCNS v1.0 (regression guard)
    ds = (prov_c or {}).get("dataset") or {}
    check("motif_provenance.dataset 锚点 MaleCNS v1.0",
          ds.get("total_synapses") == 124177617 and ds.get("annotated_neurons") == 166700,
          "ds=%s" % ds)
    # basic blueprint → source_motif = "none" (NOT biological prior)
    entry_basic = ((prov_c or {}).get("blueprint_to_motif") or {}).get("deep_reasoning") or {}
    check("basic blueprint source_motif='none'（非生物先验）",
          entry_basic.get("source_motif") == "none" and entry_basic.get("is_bio_prior") is False,
          "entry=%s" % entry_basic)
    # bio blueprint → traces to real motif with real neuron anchor
    # (regenerate a bio blueprint organism to test)
    org_bio = c1.design_organism({"n_modules": 4, "agents_per_module": 4,
                                  "module_profiles": "cycled",
                                  "blueprint": "competitive_selection"},
                                 motifs=doc, seed=7)
    cfg_bio = c1.build_swarmlabs_config(org_bio, name="bp_smoke_bio", provenance=prov)
    prov_bio = cfg_bio.get("motif_provenance")
    entry_bio = (prov_bio.get("blueprint_to_motif") or {}).get("competitive_selection") or {}
    check("bio blueprint 追溯到真实 motif（inhibitory_hub / APL body 10540）",
          entry_bio.get("source_motif") == "inhibitory_hub"
          and entry_bio.get("motif_body") == 10540
          and entry_bio.get("motif_type") == "APL"
          and entry_bio.get("motif_fanout") == 102263,
          "entry=%s" % entry_bio)
    check("bio blueprint is_bio_prior=True, bio_prior_count=1",
          prov_bio.get("is_bio_prior") is True and prov_bio.get("bio_prior_count") == 1,
          "is_bio=%s count=%d" % (prov_bio.get("is_bio_prior"), prov_bio.get("bio_prior_count")))

    # ---- schema v1.2.0: three-stage provenance (motif_synapse_stats + motif_query) ----
    # Stage 2: synapse statistics must be present for every bio blueprint
    entry_v12 = (prov_bio.get("blueprint_to_motif") or {}).get("competitive_selection") or {}
    check("v1.2.0 三段溯源 stage2: motif_synapse_stats 存在（bio 蓝图）",
          entry_v12.get("motif_synapse_stats") is not None
          and "fanout" in (entry_v12.get("motif_synapse_stats") or {}),
          "stats=%s" % entry_v12.get("motif_synapse_stats"))
    check("v1.2.0 三段溯源 stage2: percent_of_dataset_synapses 数值合理",
          0 < (entry_v12.get("motif_synapse_stats") or {}).get(
              "percent_of_dataset_synapses", 0) < 1,
          "pct=%s" % (entry_v12.get("motif_synapse_stats") or {}).get(
              "percent_of_dataset_synapses"))
    # Stage 3: runnable query must be present for every bio blueprint
    check("v1.2.0 三段溯源 stage3: motif_query 存在（bio 蓝图）",
          isinstance(entry_v12.get("motif_query"), str)
          and "SELECT" in (entry_v12.get("motif_query") or "")
          and "male_cns" in (entry_v12.get("motif_query") or ""),
          "q=%s" % entry_v12.get("motif_query"))
    # stability_target on each blueprint entry
    check("v1.2.0 每蓝图 stability_target 存在且为正数",
          all((e.get("stability_target") or 0) > 0
              for e in prov_bio["blueprint_to_motif"].values()),
          "targets=%s" % [e.get("stability_target")
                          for e in prov_bio["blueprint_to_motif"].values()])
    # cross-blueprint stability_summary with worst-case target
    stab = (prov_bio.get("stability_summary") or {})
    check("v1.2.0 stability_summary 存在（worst_case_target）",
          stab.get("worst_case_target") is not None
          and stab.get("targets_seen"),
          "stab=%s" % stab)
    check("v1.2.0 schema_version 字段为 1.2.0",
          (prov_bio.get("schema_version") == "1.2.0"),
          "v=%s" % prov_bio.get("schema_version"))
    # dataset anchor extended fields
    ds2 = (prov_bio.get("dataset") or {})
    check("v1.2.0 dataset 扩展字段：dataset_url + annotation_version",
          ds2.get("dataset_url") and ds2.get("annotation_version") == "v1.0",
          "ds=%s" % ds2)
    # synthetic blueprint: motif_synapse_stats is None (honest)
    entry_synth_v12 = (c1._motif_provenance(
        {"blueprint": "rl_actor_critic"}).get("blueprint_to_motif") or {}).get(
            "rl_actor_critic", {})
    check("v1.2.0 synthetic 蓝图 motif_synapse_stats=None（诚实标记）",
          entry_synth_v12.get("motif_synapse_stats") is None
          and entry_synth_v12.get("motif_query") is None,
          "entry=%s" % entry_synth_v12)
    # 3 new Phase 4 stability-optimized blueprints exist and are biological
    new_bps = ["modular_isolation", "robust_redundant", "decoupled_hierarchical"]
    check("v1.2.0 Phase 4 三个稳定性蓝图存在",
          all(k in c1.BLUEPRINTS for k in new_bps),
          "have=%s" % [k for k in new_bps if k in c1.BLUEPRINTS])
    # all three new blueprints trace to a real motif
    prov_new = c1._motif_provenance({"blueprint": "+".join(new_bps)})
    check("v1.2.0 三个新蓝图均追溯到真实 motif（非 none）",
          all((e.get("source_motif") or "none") != "none"
              for e in prov_new["blueprint_to_motif"].values()),
          "motifs=%s" % [(e.get("source_motif"), e.get("motif_body"))
                         for e in prov_new["blueprint_to_motif"].values()])
    # stability_target ordering: isolated (最严格) < redundant < decoupled
    # (分层结构必然跨模块边更多；冗余 fanout 在模块内密度更高)
    targets = {k: prov_new["blueprint_to_motif"][k].get("stability_target")
               for k in new_bps}
    check("v1.2.0 稳定性目标严格递增（isolation < redundant < decoupled）",
          targets["modular_isolation"] < targets["robust_redundant"]
          < targets["decoupled_hierarchical"],
          "targets=%s" % targets)

    # ---- v1.2.0 stability check: cross_module_edge_ratio vs target ----
    # For each of the 3 new stability-optimized blueprints, verify the
    # actual cross-module edge ratio respects its design target.
    stability_results = {}
    for bp in new_bps:
        org_stab = c1.design_organism(
            {"n_modules": 5, "agents_per_module": 5,
             "module_profiles": "cycled", "blueprint": bp},
            motifs=doc, seed=7)
        ratio = cross_module_edge_ratio(org_stab, 5)
        stability_results[bp] = ratio
        tgt = prov_new["blueprint_to_motif"][bp].get("stability_target", 1.0)
        check("v1.2.0 稳定性达标：%-24s ratio≤target (%.4f≤%.2f)" % (
            bp, ratio, tgt),
            ratio <= tgt + 1e-9,
            "ratio=%.4f target=%.2f" % (ratio, tgt))
    check("v1.2.0 稳定性排序实测：isolation < redundant < decoupled",
          stability_results["modular_isolation"] <= stability_results["robust_redundant"]
          <= stability_results["decoupled_hierarchical"],
          "ratios=%s" % stability_results)

    # ---- v1.2.1: W3C PROV-JSON (via dataprov) ---------------------------- #
    # Standardize provenance to W3C PROV-JSON — the international standard
    # that any provenance-aware tool (yProv4ML, MLflow2PROV, MIT Sloan
    # Data Provenance Explorer, PROV-O SPARQL endpoints) can ingest.
    # EU AI Act compliance hard gate: provenance must be W3C-standard.
    cfg_prov = c1.build_swarmlabs_config(
        c1.design_organism({"n_modules": 5, "agents_per_module": 5,
                            "module_profiles": "cycled",
                            "blueprint": "modular_isolation"},
                           motifs=None, seed=7),
        name="smoke_prov", provenance=None)
    prov_json = cfg_prov.get("prov_json")
    check("v1.2.1 prov_json 字段存在（dataprov 可用时）",
          prov_json is not None,
          "prov_json=%s" % ("present" if prov_json else "None (dataprov missing?)"))
    if prov_json:
        check("v1.2.1 prov_json 含 W3C PROV-JSON prefix (prov 命名空间)",
              "prov" in prov_json.get("prefix", {}),
              "prefix=%s" % prov_json.get("prefix"))
        check("v1.2.1 prov_json 含 dataprov:metadata (版本 + 时间戳)",
              "dataprov:metadata" in prov_json
              and prov_json["dataprov:metadata"].get("version"),
              "metadata=%s" % prov_json.get("dataprov:metadata"))
        check("v1.2.1 prov_json 含 PROV 核心关系（wasDerivedFrom + wasAssociatedWith + wasAttributedTo）",
              all(k in prov_json for k in
                  ["wasDerivedFrom", "wasAssociatedWith", "wasAttributedTo"]),
              "keys=%s" % [k for k in ["wasDerivedFrom", "wasAssociatedWith",
                                        "wasAttributedTo", "wasGeneratedBy"]
                            if k in prov_json])
        check("v1.2.1 prov_json entity 至少含 dataset 锚点 + blueprint motif",
              len(prov_json.get("entity", {})) >= 2,
              "entities=%d: %s" % (len(prov_json.get("entity", {})),
                                   list(prov_json.get("entity", {}).keys())[:3]))
        check("v1.2.1 prov_json activity 至少含 1 步（blueprint extraction 或 synthesis）",
              len(prov_json.get("activity", {})) >= 1,
              "activities=%d" % len(prov_json.get("activity", {})))
        check("v1.2.1 prov_json agent 含 flybrain-connectome 工具",
              any("flybrain" in k.lower() or "flybrain" in json.dumps(v).lower()
                  for k, v in prov_json.get("agent", {}).items()),
              "agents=%s" % list(prov_json.get("agent", {}).keys()))
        check("v1.2.1 prov_json wasDerivedFrom 关系非空（数据溯源链）",
              len(prov_json.get("wasDerivedFrom", {})) >= 1,
              "derivations=%d" % len(prov_json.get("wasDerivedFrom", {})))
        check("v1.2.1 prov_json flybrain:dataset_anchor 含 MaleCNS v1.0 锚点",
              prov_json.get("flybrain:dataset_anchor", {}).get("name") == "MaleCNS v1.0"
              and prov_json.get("flybrain:dataset_anchor", {})
                     .get("total_synapses") == 124177617,
              "anchor=%s" % prov_json.get("flybrain:dataset_anchor"))
        # PROV-JSON schema validation via dataprov's own validator
        try:
            from dataprov import ProvenanceChain
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), "_prov_validate.json")
            with open(tmp, "w") as f:
                json.dump(prov_json, f)
            chain = ProvenanceChain.load(tmp)
            chain.validate()
            check("v1.2.1 prov_json 通过 dataprov 官方 schema 校验",
                  True, "dataprov.validate() OK")
            try:
                os.remove(tmp)
            except OSError:
                pass
        except ImportError:
            print("  %-46s SKIP  (dataprov 不可用)" % "prov_json 官方 schema 校验")
        except Exception as e:  # noqa: BLE001
            check("v1.2.1 prov_json 通过 dataprov 官方 schema 校验",
                  False, "validation failed: %s" % e)

    # ---- schema v1.1: task_hint / edge.semantic / module.capability ----
    check("swarm.json schema_version == 1.2.1",
          cfg_c.get("schema_version") == "1.2.1",
          "version=%s" % cfg_c.get("schema_version"))
    agents_with_hint = [a for a in cfg_c["swarm"]["agents"] if a.get("task_hint")]
    check("agent.task_hint 全量存在",
          len(agents_with_hint) == len(cfg_c["swarm"]["agents"]),
          "agents_with_hint=%d/%d" % (len(agents_with_hint),
                                      len(cfg_c["swarm"]["agents"])))
    edges_with_semantic = [e for e in cfg_c["swarm"]["edges"] if e.get("semantic")]
    check("edge.semantic 全量存在",
          len(edges_with_semantic) == len(cfg_c["swarm"]["edges"]),
          "edges_with_semantic=%d/%d" % (len(edges_with_semantic),
                                         len(cfg_c["swarm"]["edges"])))
    modules_with_cap = [m for m in cfg_c["swarm"]["modules"] if m.get("capability")]
    check("module.capability 全量存在",
          len(modules_with_cap) == len(cfg_c["swarm"]["modules"]),
          "modules_with_cap=%d/%d" % (len(modules_with_cap),
                                      len(cfg_c["swarm"]["modules"])))

    cfg = c1.build_swarmlabs_config(org, name="smoke_test", provenance=prov)
    v = cfg["swarm"]["validation"]
    check("SwarmLabs config 自检 ok", v["ok"] is True,
          "agents=%d edges=%d leader=%s" % (v["n_agents"], v["n_edges"],
                                            v["leader_resolved"]))
    check("无悬空边", v["dangling_edges"] == 0)
    check("边权全在 [-1,1]", v["weights_in_range"] is True,
          "[%s, %s]" % (v["weight_min"], v["weight_max"]))
    check("leader 不在任何模块内", v["leader_is_module_member"] is False)

    # ---- 5. YAML 与 JSON 等价（若 PyYAML 可用） -------------------- #
    try:
        import yaml
        y = yaml.safe_load(c1.yaml_dump(cfg))
        check("yaml_dump 与 JSON 对象等价", y == cfg)
    except ImportError:
        print("  %-46s SKIP  (PyYAML 不在环境中)" % "yaml_dump round-trip")

    # ---- 汇总 ------------------------------------------------------ #
    failed = [r for r in RESULTS if not r[1]]
    print("\n%s  %d/%d 通过%s\n" % (
        "全部通过 ✓" if not failed else "存在失败 ✗",
        len(RESULTS) - len(failed), len(RESULTS),
        "" if not failed else "  -> " + ", ".join(r[0] for r in failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
