"""
A1: 数据驱动的模块发现原型。
用双模态特征聚类 27 个 superclass：
  - 连接谱：row/col 归一化的 27 维出/入分布（结构指纹）
  - 递质谱：该 superclass 内神经元的 7 类递质分布（功能指纹）
  - 自循环率：模块内部记忆强度
方法：Louvain 社区发现（网络视角）+ 层次聚类（特征视角）
输出：候选"最小功能单元"分组，并与现有 19 个 hand-crafted 模块对照。
"""
import json
import numpy as np
import networkx as nx
from pathlib import Path
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
MALE = ROOT / "male_cns"
CACHE = MALE / "connectome_cache"

mat = json.loads((MALE / "superclass_matrix.json").read_text(encoding="utf-8"))
sc = mat["superclass_list"]
N = len(sc)
M = np.array(mat["matrix"], dtype=np.float64)
total = M.sum()

lines = []
def p(s=""):
    lines.append(str(s))

p("=" * 78)
p("A1  双模态模块发现")
p("=" * 78)
p(f"superclass N={N}  matrix_syn={M.sum():,.0f}")

# ---------------- 递质谱 per superclass ----------------
nt_raw = json.loads((CACHE / "nt.json").read_text(encoding="utf-8"))
ann = json.loads((CACHE / "annotations.json").read_text(encoding="utf-8"))
NT_KINDS = ["acetylcholine", "dopamine", "gaba", "glutamate",
            "histamine", "octopamine", "serotonin"]
sc_nt = {s: Counter() for s in sc}
n_nt_total = 0
for body, rec in ann.items():
    s = rec.get("superclass")
    if not s or s not in sc_nt:
        continue
    nt = nt_raw.get(str(body)) or nt_raw.get(int(body))
    if isinstance(nt, list):
        nt = nt[0] if nt else None
    if not nt:
        continue
    key = str(nt).strip().lower()
    if key in NT_KINDS:
        sc_nt[s][key] += 1
        n_nt_total += 1
p(f"神经元递质标注覆盖 = {n_nt_total:,} 个")

# ---------------- 特征矩阵 ----------------
out_prof = M / np.maximum(M.sum(axis=1, keepdims=True), 1)
in_prof = M / np.maximum(M.sum(axis=0, keepdims=True), 1)
self_ratio = np.array([M[i, i] / max(M[i].sum(), 1) for i in range(N)])
nt_prof = np.zeros((N, len(NT_KINDS)))
for i, s in enumerate(sc):
    tot = sum(sc_nt[s].values())
    if tot:
        for j, k in enumerate(NT_KINDS):
            nt_prof[i, j] = sc_nt[s][k] / tot

feat = np.hstack([out_prof, in_prof, self_ratio[:, None], nt_prof])
p(f"特征维度 = {feat.shape[1]}  (out27 + in27 + self1 + nt7)")

# ---------------- 方法1: Louvain (结构视角) ----------------
G = nx.Graph()
G.add_nodes_from(sc)
for i in range(N):
    for j in range(i + 1, N):
        wgt = M[i, j] + M[j, i]
        if wgt > 0:
            G.add_edge(sc[i], sc[j], weight=float(wgt))
louvain = nx.community.louvain_communities(G, weight="weight", seed=42)
lou_mod = nx.community.modularity(G, louvain, weight="weight")
louvain = sorted(louvain, key=len, reverse=True)

p()
p(f"-- 方法1 Louvain 社区（结构视角）--")
p(f"   发现 {len(louvain)} 个社区, modularity Q = {lou_mod:.4f}")
for k, com in enumerate(louvain, 1):
    mem = sorted(com, key=lambda s: -sum(M[sc.index(s)]))
    tot = sum(M[sc.index(s)].sum() for s in mem)
    p(f"   C{k}: n={len(mem):<2} syn={tot:>12,.0f} ({100*tot/total:5.2f}%)  {mem}")

# ---------------- 方法2: 层次聚类 (特征视角) ----------------
Z = linkage(feat, method="ward")
p()
p("-- 方法2 Ward 层次聚类（特征视角）--")
for k in (4, 6, 8, 10):
    lab = fcluster(Z, k, criterion="maxclust")
    groups = {}
    for i, c in enumerate(lab):
        groups.setdefault(c, []).append(sc[i])
    p(f"   k={k}:")
    for c in sorted(groups, key=lambda c: -sum(M[sc.index(s)].sum() for s in groups[c])):
        mem = sorted(groups[c], key=lambda s: -sum(M[sc.index(s)]))
        tot = sum(M[sc.index(s)].sum() for s in mem)
        p(f"      n={len(mem):<2} syn={tot:>12,.0f} ({100*tot/total:5.2f}%)  {mem}")

# ---------------- 每个 superclass 的功能指纹 ----------------
p()
p("-- 27 superclass 的结构+功能指纹（出度/自循环/主递质）--")
p(f"  {'superclass':<24} {'out_syn':>12} {'self%':>6}  {'主递质':<14} {'n_nt':>6}")
order = sorted(range(N), key=lambda i: -M[i].sum())
for i in order:
    s = sc[i]
    nt_c = sc_nt[s]
    tot_nt = sum(nt_c.values())
    if tot_nt:
        t, c = nt_c.most_common(1)[0]
        nt_str = f"{t}({c/tot_nt:.2f})"
    else:
        nt_str = "-"
    p(f"  {s:<24} {M[i].sum():>12,.0f} {100*self_ratio[i]:>5.1f}%  {nt_str:<14} {tot_nt:>6,}")

# ---------------- 与现有 19 模块对照 ----------------
p()
p("=" * 78)
p("对照：现有 19 hand-crafted 模块")
p("=" * 78)
import sys
sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))
from module_registry import MODULE_REGISTRY, PRESETS
p(f"MODULE_REGISTRY = {len(MODULE_REGISTRY)} 模块, PRESETS = {len(PRESETS)}")
p(f"模块名 ∩ superclass = {set(MODULE_REGISTRY) & set(sc)}")
p()
p("19 模块的 motif_source 分布:")
src = Counter(spec.motif_source for spec in MODULE_REGISTRY.values())
for k, v in src.most_common():
    p(f"   {k:<24} {v}")

# 数据发现的"结构性单元"候选（出度 > 1M 或自循环 > 5%）
p()
p("-- 数据支持的结构性单元（出突触 > 1M 或 自循环 > 5%）--")
structural = []
for i, s in enumerate(sc):
    if M[i].sum() > 1_000_000 or self_ratio[i] > 0.05:
        structural.append(s)
p(f"   共 {len(structural)} 个: {structural}")

_rep = ROOT / "tmp" / "module_discovery_result.txt"
_rep.parent.mkdir(parents=True, exist_ok=True)
_rep.write_text("\n".join(lines), encoding="utf-8")
print("done")
