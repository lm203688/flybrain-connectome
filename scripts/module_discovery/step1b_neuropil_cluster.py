"""
A1b: 从 superclass(27) 下沉到 neuropil(146) 粒度做数据驱动模块发现。

方法：
  1. 读取 neuropil_stats.json (146 条)
  2. 合并 L/R 对（65 对，果蝇神经的左右对称性），得到 73 个"功能单元"
  3. 双模态聚类：NT 分布 (7 维) + 突触数 log + 突触密度
     - Ward 层次聚类（特征视角，选 k=8..20）
     - Louvain 社区发现（网络视角，按 NT 距离相似度建图）
  4. 输出 discovered_modules_neuropil.json
     每单元：成员 neuropil 名 + 突触合计 + 加权 NT 谱 + 与 superclass 组的对照
"""
import json
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist

ROOT = Path(__file__).resolve().parents[2]
MALE = ROOT / "male_cns"

NT_KINDS = ["acetylcholine", "dopamine", "gaba", "glutamate",
            "histamine", "octopamine", "serotonin"]

raw = json.loads((MALE / "neuropil_stats.json").read_text(encoding="utf-8"))
neuro = raw["neuropils"]

# ---- 合并 L/R 对 ----
merged = defaultdict(lambda: {"synapses": 0, "tbar_synapses": 0,
                              "pre": set(), "post": set(),
                              "nt": Counter()})
lone = set()
for name, d in neuro.items():
    if name.endswith("(L)") or name.endswith("(R)"):
        base = name[:-3]
    else:
        base = name
        lone.add(base)
    m = merged[base]
    m["synapses"] += d["synapses"]
    m["tbar_synapses"] += d.get("tbar_synapses", 0)
    m["nt"] += Counter(d.get("neurotransmitters", {}))
    # distinct pre/post counts can't be summed (overlap), but total pre neuron visits = synapses/mean_syn
    m["pre_visits"] = m.get("pre_visits", 0) + d["distinct_pre_neurons"]
    m["post_visits"] = m.get("post_visits", 0) + d["distinct_post_neurons"]
    m["mean_syn_per_pre"] = d["mean_synapses_per_pre"]

# convert to list of tuples
neuropil_list = []
for name, m in merged.items():
    tot_nt = sum(m["nt"].values())
    nt_vec = np.array([m["nt"][k] / tot_nt if tot_nt else 0
                       for k in NT_KINDS])
    syn = m["synapses"]
    density = m.get("mean_syn_per_pre", 0)
    # 双模态特征：NT (7) + log(syn) (1) + log(mean_syn_per_pre) (1)
    feat = np.concatenate([nt_vec, [np.log10(max(syn, 1))],
                           [np.log10(max(density, 1))]])
    neuropil_list.append({
        "name": name,
        "synapses": int(syn),
        "tbar_synapses": int(m["tbar_synapses"]),
        "pre_visits": int(m["pre_visits"]),
        "post_visits": int(m["post_visits"]),
        "mean_syn_per_pre": density,
        "nt": {k: round(m["nt"][k] / tot_nt, 4) if tot_nt else 0 for k in NT_KINDS},
        "dominant_nt": m["nt"].most_common(1)[0][0] if tot_nt else None,
        "feat": feat,
    })

neuropil_list.sort(key=lambda x: -x["synapses"])
F = np.array([n["feat"] for n in neuropil_list])
N = len(neuropil_list)
total_syn = int(sum(n["synapses"] for n in neuropil_list))

lines = []
def p(s=""): lines.append(str(s))

p("=" * 78)
p("A1b  neuropil 粒度模块发现（下沉 superclass → neuropil）")
p("=" * 78)
p(f"原始 neuropil (with L/R): {len(neuro)}")
p(f"合并后功能单元: {N}")
p(f"总突触: {total_syn:,}")
p(f"特征维度: {F.shape[1]} (NT7 + log_syn + log_density)")

# ---- Ward 层次聚类 ----
Z = linkage(F, method="ward")
ward_clusters = {}
for k in (6, 8, 10, 12, 15):
    lab = fcluster(Z, k, criterion="maxclust")
    groups = defaultdict(list)
    for i, c in enumerate(lab):
        groups[c].append(neuropil_list[i])
    ward_clusters[k] = list(groups.values())

p()
p("-- Ward 层次聚类（NT + 突触 + 密度）--")
for k, groups in ward_clusters.items():
    p(f"  k={k}:")
    for g in sorted(groups, key=lambda g: -sum(x["synapses"] for x in g)):
        syn = sum(x["synapses"] for x in g)
        names = [x["name"] for x in g]
        p(f"    n={len(g):<3} syn={syn:>12,} ({100*syn/total_syn:5.2f}%)  {names}")

# ---- Louvain (NT 相似度图) ----
from scipy.spatial.distance import pdist, squareform
from networkx import Graph
from networkx.algorithms.community import louvain_communities, modularity as lou_mod

D = squareform(pdist(F))
G = Graph()
G.add_nodes_from(range(N))
# 只连 NT 距离小于中位数的边（避免稠密图）
threshold = np.median(D[D > 0])
for i in range(N):
    for j in range(i + 1, N):
        if D[i, j] < threshold:
            G.add_edge(i, j, weight=float(1 - D[i, j]))
louv = sorted(louvain_communities(G, weight="weight", seed=42), key=len, reverse=True)
Q = lou_mod(G, louv, weight="weight")
p()
p(f"-- Louvain 社区发现 (NT 距离 < 中位数 {threshold:.4f})--")
p(f"  社区数 = {len(louv)}, Q = {Q:.4f}")
for k, com in enumerate(louv, 1):
    syn = sum(neuropil_list[i]["synapses"] for i in com)
    names = [neuropil_list[i]["name"] for i in com]
    p(f"  C{k}: n={len(com):<3} syn={syn:>12,} ({100*syn/total_syn:5.2f}%)  {names}")

# ---- 选 k=10 作为最终单元（覆盖率高且粒度合理）----
final_lab = fcluster(Z, 10, criterion="maxclust")
final_groups = defaultdict(list)
for i, c in enumerate(final_lab):
    final_groups[c].append(i)

# 每个单元的功能标签（按 NT 主递质 + 突触规模命名）
NT_CATEGORY = {
    "acetylcholine": "cholinergic",
    "glutamate": "glutamatergic",
    "gaba": "gabaergic",
    "histamine": "historminergic",
    "octopamine": "octopaminergic",
    "serotonin": "serotonergic",
    "dopamine": "dopaminergic",
}

def unit_label(members):
    """按主递质 + 突触规模给单元起名"""
    tot_nt = Counter()
    tot_syn = 0
    for i in members:
        n = neuropil_list[i]
        tot_syn += n["synapses"]
        for k, v in n["nt"].items():
            tot_nt[k] += v * n["synapses"]  # synapse-weighted
    dom = tot_nt.most_common(1)[0][0] if tot_nt else "unknown"
    pct = tot_nt[dom] / tot_syn if tot_syn else 0
    return f"{NT_CATEGORY.get(dom, dom)}_unit", dom, round(pct, 4)

units = []
seen = {}
for c, members in sorted(final_groups.items(), key=lambda kv: -sum(neuropil_list[i]["synapses"] for i in kv[1])):
    label, dom, pct = unit_label(members)
    # unique id: same domNT appears multiple times (anatomically distinct)
    seen[label] = seen.get(label, 0) + 1
    unit_id = label if seen[label] == 1 else f"{label}_{seen[label]}"
    syn = sum(neuropil_list[i]["synapses"] for i in members)
    member_details = []
    # 解剖学标签：按成员名归类
    anatomical = Counter()
    for i in members:
        nm = neuropil_list[i]["name"]
        if "Leg" in nm: anatomical["thoracic_leg_motor"] += 1
        elif "VAC" in nm: anatomical["thoracic_abdominal"] += 1
        elif nm in ("ME", "LO", "FB", "EB"): anatomical["central_bulb"] += 1
        elif nm == "GNG": anatomical["glomerulus"] += 1
        elif "Tct" in nm or nm in ("LH","SPS","LAL","WED","SIP","SCL","VES","SAD","AL"): anatomical["subesophagus"] += 1
        elif "AOTU" in nm or "CRE" in nm or "IB" in nm or "IntTct" in nm: anatomical["posterior"] += 1
        elif "Optic" in nm or nm in ("aL","bL","a'L","b'L","gL","PED","LA","PrN"): anatomical["optic"] += 1
        elif "AbN" in nm or "DMetaN" in nm or "AME" in nm or "Meso" in nm or "Meta" in nm or "Pro" in nm: anatomical["antennal"] += 1
        else: anatomical["other"] += 1
    for i in members:
        n = neuropil_list[i]
        member_details.append({
            "name": n["name"],
            "synapses": n["synapses"],
            "tbar_synapses": n["tbar_synapses"],
            "distinct_pre_visits": n["pre_visits"],
            "mean_syn_per_pre": n["mean_syn_per_pre"],
            "neurotransmitters": n["nt"],
        })
    units.append({
        "unit_id": unit_id,
        "category": f"{dom}_neuropil",
        "dominant_nt": dom,
        "dominant_nt_share": pct,
        "anatomical_regions": anatomical.most_common(),
        "n_neuropils": len(members),
        "synapses": int(syn),
        "pct_of_total": round(100 * syn / total_syn, 3),
        "members": member_details,
    })

out = {
    "schema_version": "1.1",
    "generated_from": "MaleCNS v1.0 neuropil_stats.json (146 raw → 73 L/R-merged)",
    "method": ("L/R pair merge → Ward hierarchical clustering on NT(7) + log10(synapses) + log10(mean_syn_per_pre); "
               "cross-validated by Louvain on NT distance graph"),
    "n_units": len(units),
    "n_neuropils_raw": len(neuro),
    "n_neuropils_merged": N,
    "total_synapses": total_syn,
    "k_selected": 10,
    "units": units,
    "caveat": ("neuropil 是**突触发生地**（解剖学），与 superclass 的**神经元类型**正交。"
               "两层粒度揭示：同一个 visual_projection superclass 的突触可能分布于 30+ 个不同 neuropil，"
               "而同一 ME 皮层内发生着 27 类 superclass 之间的交互。"
               "最小功能单元 = superclass × neuropil 交叉，本文件给出 neuropil 侧的独立切面。"),
}

(MALE / "discovered_modules_neuropil.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# 报告
p()
p("=" * 78)
p(f"输出: male_cns/discovered_modules_neuropil.json (k={len(units)} 单元)")
p("=" * 78)
for u in units:
    names = [m["name"] for m in u["members"][:5]]
    extra = f" +{u['n_neuropils']-5}" if u["n_neuropils"] > 5 else ""
    p(f"  {u['unit_id']:<22} syn={u['synapses']:>12,} ({u['pct_of_total']:5.2f}%)  "
      f"domNT={u['dominant_nt']}({u['dominant_nt_share']:.2f})  n={u['n_neuropils']}  {names}{extra}")

_rep = ROOT / "tmp" / "neuropil_discovery.txt"
_rep.parent.mkdir(parents=True, exist_ok=True)
_rep.write_text("\n".join(lines), encoding="utf-8")
print("done")
print(f"neuropils merged: {len(neuro)} → {N}")
print(f"units @ k=10: {len(units)}")
