# Zebrafish Whole-Brain EM Connectome: Feasibility (v2.46.0) + Authorization (v2.48.0)

**目的**：判断"加入第四个连接组 = 斑马鱼全脑 EM"是否可行，与已有三个连接组的分工，以及拉数据之前必须先确认的事。

**结论先行**：
- ✅ **数据可访问**：两个 2025 年公开 EM 源，Google Cloud / 中科院开放平台，CC-BY-NC 4.0
- ⚠️ **数据量级不适合本地全量**：30M synapses / 180k soma，需要采样策略
- ✅ **补齐的维度真实**：三个已有连接组都没有分子级 E/I 标注，斑马鱼是**脊椎动物首次 EM 级证据**
- ⚠️ **不能替代 MaleCNS 主力锚定**：116 单元的锚定 37 条全部来自 MaleCNS，斑马鱼是**独立证据源**，用来跨物种验证 circuit 是否守恒
- ✅ **本轮已拉采样数据**（v2.48.0）：Petkova 2025 fish1-release 的 TEN + HMI 分析包已落 Tier-2

---

## 数据源核实

### 源 A：Petkova et al. 2025（Janelia / ZFIN 联盟）

- **DOI**：10.1101/2025.06.10.658982
- **入口**：`https://fish1-release.storage.googleapis.com/index.html`（Google Cloud 公开桶）
- **平台**：open-access platform（Janelia Fish Connectome）
- **许可**：CC-BY-NC 4.0（禁止商业使用，与本项目 MIT 主许可冲突，需要单独处理）

**规模**：

| 维度 | 数值 |
|---|---|
| 分节 soma | >180,000 |
| 分子注释神经元 | >40,000（vglut2a 兴奋 / gad1b 抑制） |
| 突触 | ~30,000,000 |
| 递质分类 | 兴奋 / 抑制 / 调节 |
| 覆盖 | 全脑 + 前脊髓 |
| 方法 | CLEM（共聚焦 + 逐层 EM） |

**独有的三个维度**（三个已有连接组都没有）：
1. **每个 soma 带分子标签**：`vglut2a`（谷氨酸能，兴奋）/ `gad1b`（GABA 能，抑制）——本项目第一次可以声明**兴奋 vs 抑制**级别的 circuit
2. **递质三分类**：兴奋 / 抑制 / 调节——本项目的 `CONNECTION_TYPES` 里没有直接对应，需要新增 `excitatory_synapse` / `inhibitory_synapse`
3. **input / output drive index**：作者在单细胞分辨率算好了输入/输出驱动度，可以直接映射成 `PORT_TYPES` 里的强度信息

**作者示范的三个 circuit**（可直接抽成 unit 模板）：
- **侧线水流方向编码**（lateral line water flow）——本项目没有侧线单元，是新功能类别
- **后脑运动整合器**（hindbrain motion integrator, HMI）——recurrent excitation + contralateral inhibition，可对比本项目已有的视觉通路
- **被盖兴奋核远距离投射**（tegmental excitatory nucleus, TEN）——功能相关的长距离 projection，可对比本项目已有的 association cortex 单元

### 源 B：Zhang / Li et al. 2025（上海交大 / 中科院）

- **DOI**：10.1101/2025.06.12.659365
- **许可**：bioRxiv preprint，数据源未在摘要中给出（需二次核实）

**规模**：

| 维度 | 数值 |
|---|---|
| 分节神经元 | >170,000 |
| 突触 | ~25,000,000 |
| 神经调节亚型 | NA / DA / 5HT / orexin / glycinergic 五种 |
| 全脑 | 脊椎动物全脑 EM + 分子注释 |

**独有**：五种神经调节分子的亚型标注（NA 去甲肾上腺素、DA 多巴胺、5HT 5-羟色胺、orexin 食欲素、glycine 甘氨酸）——本项目的 `neuromodulation` domain 目前只有 4 个单元（dopaminergic_value / octopamine_arousal / locus_coeruleus_arousal 等），斑马鱼可以补齐 **5-HT / orexin** 两个跨物种证据。

**风险**：数据入口未在摘要披露，需要作者主页二次核实；如果只挂在 bioRxiv 没有独立平台，落地路径不明。

---

## 与三个已有连接组的分工

| 连接组 | 物种 | 神经元 | 突触 | 阶段 | 分子标签 | 用途 |
|---|---|---|---|---|---|---|
| MaleCNS | Drosophila 成虫 | 166,700 | 124M | 成虫雄性 | 无 E/I | **主力锚定**（37/115 单元） |
| Witvliet 2020 | C. elegans | 302 | 1,980 | 成虫×2 + L1×4 + L2/L3 | 无 | 发育阶段轴 |
| Winding 2023 | Drosophila 幼虫 | 2,956 | 352,611 | 幼虫 | 有 polarity（ad/aa/da/dd） | 幼虫阶段 + polarity |
| **Petkova 2025** | **Zebrafish 幼虫** | **180,000** | **30M** | **7-day larva** | **有 E/I + 递质分类** | **脊椎动物首证** |

**斑马鱼加入后新增的三个维度**：
1. **脊椎动物 EM 级证据**——现有三个都是 invertebrate；斑马鱼是唯一 vertebrate
2. **E/I 极性**——MaleCNS/C. elegans/larva 都没有，只有 zebrafish 有
3. **神经调节分子亚型**——现有 `neuromodulatory` domain 只有泛化标签，斑马鱼给具体分子

**不替代任何已有证据**：斑马鱼是**独立第四源**，不合并进 MaleCNS 锚定。116 单元的 37 条锚定仍然全部来自 MaleCNS；斑马鱼只提供跨物种一致性检查（同 circuit 在脊椎动物里是否存在）。

---

## 数据量级估算与采样策略

**全量下载估算**：
- Petkova：30M synapses × ~200 bytes/synapse = **6 GB**（保守）
- 加上 180k soma 形态 + 分子标签 = **再加 2 GB**
- **总计 ~8 GB**——不适合放 Tier-2 私有仓（当前 MaleCNS 5.63 GB 是单一大文件）

**采样策略**（本项目实际用的量级）：

| 阶段 | 数据 | 大小 | 用途 |
|---|---|---|---|
| 元数据 | fish1-release 目录清单 + 分片索引 | ~10 MB | 判断需要拉哪些 slice |
| 分子标签表 | 40k annotated somas 的 `vgLut2a/gad1b` 分类 | ~50 MB | 建分子注释索引 |
| 局部 edge 子集 | 每个示范 circuit 的邻域（3 个 circuit） | ~500 MB | 抽 3-5 个单元 |
| Drive index 表 | 输入/输出驱动度 per-soma | ~5 MB | 映射到 PORT_TYPES |
| 全量突触矩阵 | 30M synapses | 6 GB | **不落地**，只在作者平台查询 |

**实际策略**：不下载全量矩阵，只用作者平台的**查询接口**（如果开放）+ 元数据 + 分子标签 + 3 个示范 circuit 邻域。总本地数据 ~600 MB，符合项目当前体量。

---

## CC-BY-NC 授权边界决策（v2.48.0 定稿）

Petkova 2025 走 CC-BY-NC 4.0（非商业），本项目主许可走 MIT（含商业）。这是**代码许可 vs 数据许可**的分离问题——不是代码本身的商业性，是**数据再分发**的边界。

**已核实的事实**：
- Google Cloud 桶 `fish1-release.storage.googleapis.com` **匿名可读**（HEAD 200 + ListBucket 成功）
- 桶根目录只放 HTML 页面 + paper_data 三个小 zip（HMI 1.4 MB / TEN 3.5 MB / vast segmentation 3.5 GB 不下载）
- 全量 30M synapse 数据**不在桶里**，走 `brain-wire-test.org` CAVE 平台，需要 OAuth token

**决策：方案 (a) — 数据存 Tier-2 私有仓，代码保持 MIT，README 显式声明数据源许可**

理由：
1. **MIT 代码 + CC-BY-NC 数据可以共存**——MIT 只约束本项目代码本身；数据源许可在数据的 `provenance.source_license` 里显式声明，与代码库主许可正交
2. **Tier-2 私有仓保护数据边界**——`flybrain-connectome-core` 私有仓承载 `zebrafish_data/`（本次只落采样包，~5 MB），公开仓 `flybrain-connectome` 只放代码 + 骨架 + 抽样统计；不复制作者原始数据到公开层
3. **不新增 CONNECTION_TYPES**（v2.48.0 决策）——TEN + HMI 单元在 v2.48.0 只声明**统计性描述**（soma 数 / 分子分布 / 内/外部边比例），不落到 `CONNECTION_TYPES` 词汇。等 3-5 个电路全部落地并复核后再补 `excitatory_synapse` / `inhibitory_synapse`

**隔离措施**：
- `zebrafish_data/` 目录走 `.gitignore`（不进主仓）；本地 Tier-2 存
- 抽样统计落到 `zebrafish_profiles.json`，走 MIT（数据派生的元信息不受原许可约束，同 MaleCNS / Winding 处理）
- 每个 zf.* 单元在 `provenance.source_license` 显式声明 `"CC-BY-NC 4.0 — Petkova 2025"`
- `docs/zebrafish_connectome_feasibility.md` 顶部标"数据源 CC-BY-NC 4.0；本 doc 与代码 MIT"

---

## 本轮实际落地（v2.48.0）

**已拉数据**：
- `zebrafish_data/paper_data/HMI_analysis.zip` (1.4 MB) — Hindbrain Motion Integrator 分析包
- `zebrafish_data/paper_data/TEN_analysis.zip` (3.5 MB) — Tegmental Excitatory Nucleus 分析包
- **不下载**：`vast/OC_left.vsseg` + `OC_right.vsseg` (3.5 GB)，全量矩阵在 CAVE 平台不在桶里

**已抽 2 个 zf 单元**（`flybrain-connectome-mcp/functional_units/zebrafish_profiles.json`）：
1. `zf_tegmental_excitatory_nucleus_unit`（TEN，110 neurons / 4 class / 26 intra-TEN edges / 5156 external endpoints，是**远距离投射核**不是 recurrent loop——重要发现）
2. `zf_hindbrain_motion_integrator_unit`（HMI，178 fully reconstructed / 60 VGluT2 excitatory + 75 Gad1B inhibitory，带 forward/turning motion spine 分类）

**未抽**：侧线水流方向编码（lateral line）——数据里只有 HMI + TEN 两个示范分析包，侧线需要另拉数据源（作者平台 CAVE 或 Zhang/Li 2025 未核实入口）

**FUNCTIONAL_UNITS 变化**：116 → 118。14 门禁全绿。

---

## 下一步（v2.49+）

1. **补第三个 zf 单元**：从 CAVE 平台拉 lateral line 数据（需要用户提供 OAuth token 或走 Zhang/Li 2025 独立入口）
2. **补 neuromodulation 亚型**：从 Zhang/Li 2025 拉 NA/DA/5HT/orexin/glycine 五种神经调节分子标注，扩到 `neuromodulatory` domain
3. **补 CONNECTION_TYPES 词汇**：把 `excitatory_synapse` / `inhibitory_synapse` 加入 `CONNECTION_TYPES`，把 TEN/HMI 单元的内部边从"统计描述"升级到"词汇声明"
4. **跨物种证据链**：把 zf.* 单元的 `cross_species_evidence` 字段挂到本项目已有的 mammalian / insect 同类单元上，实现"同一 circuit 三个物种都验证"的证据等级

---

## 附录：与本项目现有代码的接入点

| 目标 | 位置 | 现状 |
|---|---|---|
| 数据存放 | `zebrafish_data/paper_data/` | 已落（v2.48.0） |
| Extractor | `scripts/extract_zebrafish_profiles.py` | 已填实现（v2.48.0） |
| Unit 落地 | `flybrain-connectome-mcp/functional_units/zebrafish_profiles.json` | 已生成（v2.48.0） |
| Gen 接入 | `scripts/gen_functional_units.py::_load_connectome_units` | 已注册（v2.48.0） |
| 门禁断言 | `scripts/check_functional_units.py` | 单元数 116 → 118（v2.48.0） |
| README 声明 | `README.md` 顶部 | 已加 CC-BY-NC 数据源声明（v2.48.0） |
