# 多物种锚定采集管线前期调研报告（2026-11-02）

> **调研目的**：FlyBrain 核心目标要求"不断收集各种生物的神经元功能体系"。当前仅 3 个物种有真实连接组（果蝇成体 MaleCNS / 果蝇幼虫 / 线虫 C.elegans），40 motif 仅 3 个真实果蝇（7.5%）、116 功能单元仅 37 个真实锚定（31.9%）。本报告调研哪些物种有公开的神经元连接组/功能连接数据（可下载、许可可用），评估是否适合作为下一个连接组锚定来源。
> **执行者**：蜂群agent（SwarmCore 工程 Agent，协助 FlyBrain P1 调研）
> **日期**：2026-11-02
> **诚实声明**：本报告区分「有真实连接组数据」（经外部权威源/官方平台核实的 EM 连接组）与「仅有文献概念模式」（综述/概念框架，无突触级数据）。凡无法核实到可下载数据源的，如实标注，不夸大。

---

## 1. 结论摘要（诚实标注真实数据 vs 概念模式）

| 候选物种 | 是否真实连接组 | 数据源 | 许可 | 适合 motif 抽取 | 获取难度 |
|---|---|---|---|---|---|
| 果蝇成体 MaleCNS | ✅ 真实 | male-cns.janelia.org + GCS | CC-BY | ✅ 高 | 中（GCS 需 gsutil） |
| 果蝇幼虫（Drosophila larva） | ✅ 真实 | Zenodo 10.5281/zenodo.7473718 | CC BY | ✅ 高 | 低（Zenodo 公开） |
| 线虫 C.elegans | ✅ 真实 | Witvliet 2020 eLife + WormWiring | CC-BY-4.0 | ✅ 高 | 低（公开） |
| 斑马鱼幼虫（Danio rerio） | ✅ 真实 | Petkova 2025 bioRxiv 10.1101/2025.06.10.658982 | **CC-BY-NC-4.0** | ✅ 中高 | 低（公开） |
| 小鼠 V1 皮层 | ✅ 真实 | MICrONS v185.1（Zenodo 10.5281/zenodo.3710459） | CC-BY-4.0 | ✅ 中（子图） | 低（公开） |
| 章鱼垂直叶（Octopus vulgaris） | ✅ 真实 | Bidel 2023 eLife 12:e84257 | CC-BY-4.0 | ✅ 中（局部回路） | 低（公开） |
| 鸟类 | ❌ 无真实 EM 连接组 | — | — | ❌ | — |
| 头足类（除章鱼垂直叶） | ❌ 仅 MRI 宏观/概念 | — | — | ❌ | — |
| 哺乳动物非 V1 部分 | ❌ 仅文献概念模式 | — | — | ❌ | — |

**核心判断**：现有 3 个真实连接组之外，可作下一锚定来源的有 **斑马鱼幼虫（Petkova 2025，但注意 CC-BY-NC 非商用）**、**小鼠 V1（MICrONS，已有 B1 锁定）**、**章鱼垂直叶（Bidel 2023，局部回路）**。鸟类、头足类（除垂直叶）、哺乳动物非 V1 均无真实 EM 连接组数据，如实标注为"仅有文献概念模式"。

---

## 2. 各物种数据源明细（经外部权威源核实）

### 2.1 果蝇（Drosophila melanogaster）——已有多数据集，旗舰为 MaleCNS

果蝇是连接组学最成熟物种，多个公开数据集。数据规模与许可（来源：flyconnectome tutorial + 官方平台）：

| 数据集 | 规模 | 出处 | 许可 |
|---|---|---|---|
| **MaleCNS v1.0** | 166,700 神经元 / 6,242,118 连接 | male-cns.janelia.org（2026-06-08 官方，Cell 2026-09-03） | Data CC-BY / Code MIT |
| BANC v888 | 158,262 神经元 / 3,037,361 连接 | htem/BANC-project（GitHub） | CC-BY |
| FAFB v783 | 139,255 神经元 / 8,453 细胞类型 | Dorkenwald 2024 Nature + Schlegel 2024 Nature | CC-BY |
| MANC v1.2.1 | 23,665 神经元 / 5,305,638 连接 | flyconnectome | CC-BY |
| Hemibrain | ~25,000 神经元 | Scheffer 2020 eLife | CC-BY |

**GCS 公开存储**：`gs://lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/`（需 gsutil）。**获取难度：中**（GCS 工具链），但数据已公开。

**FlyBrain 现状**：已整合 MaleCNS（166,700 神经元 / 124,177,617 突触，CC-BY，5.63GB，`male_cns/`）。

### 2.2 果蝇幼虫（Drosophila larva）——Winding 2023 Science

- **论文**：Winding et al., *The connectome of an insect brain*, **Science 2023, 379:eadd9330**，DOI `10.1126/science.add9330`（Europe PMC PMC7614541 开放全文）。
- **规模（正式版）**：**3,016 neurons / 548,000 synapses**（abstractText，Europe PMC）。
- **数据公开**：Zenodo `10.5281/zenodo.7473718`（connectome_analysis，12.6MB）+ `10.5281/zenodo.7473710`（connectome_tools，69KB），access_right=open。
- **许可**：**CC BY**（Europe PMC structured license 字段 `"license":"cc by"`；isOpenAccess=Y）。
- **获取难度：低**（Zenodo 直接下载）。
- **FlyBrain 现状**：已有 `larva_data/raw/edges.csv`（2,952 节点 / 116,356 边），是论文数据的子集/派生。

### 2.3 线虫 C.elegans——Witvliet 2020 eLife

- **论文**：Witvliet et al., *Connectomes across development reveal principles of brain maturation*, **eLife 2020**, DOI `10.7554/eLife.47155`。
- **许可**：eLife 默认 **CC-BY-4.0**（页脚确认"Subject to a Creative Commons Attribution license"）。
- **数据**：WormWiring host 8 个重建（4 L1 + 1 L2 + 1 L3 + 2 adult）；FlyBrain 已有 `cel_data/`（elife-47155-fig9-data2-v1.csv 18节点/164边 + witvliet_2020_1-4_L1.xlsx 等 8 个重建）。
- **获取难度：低**（eLife 补充材料 + WormWiring 公开）。

### 2.4 斑马鱼幼虫（Danio rerio）——Petkova 2025

- **论文**：Petkova et al., *A connectomic resource for neural cataloguing and circuit dissection of the larval zebrafish brain*, **bioRxiv 2025-06-15**，DOI `10.1101/2025.06.10.658982`。
- **⚠️ 诚实修正**：FlyBrain 文档（`docs/arxiv_paper.md:373, :535`）把此数据源标为 **"eLife"**，但实际是 **bioRxiv 预印本**（journal-article 命中 0，无期刊正式版）。题目也非"connectomic atlas of the zebrafish optic tectum"。
- **规模**：>180,000 segmented soma / >40,000 分子注释神经元 / **30M synapses**。
- **许可**：**CC-BY-NC-4.0（禁止商用）**——bioRxiv 预印本默认，crossref license URL `http://creativecommons.org/licenses/by-nc/4.0/`。**不是纯 CC-BY**。
- **数据**：FlyBrain 已有 `zebrafish_data/paper_data/TEN_analysis`（26,593 节点 / 42,640 边），源自 Mariela Petkova（笔记本作者 displayName 确认）。
- **获取难度：低**（bioRxiv 公开）。
- **⚠️ 商用注意**：CC-BY-NC 意味着 FlyBrain 若用于商业/闭源用途受限制；学术用途可。

### 2.5 小鼠 V1 皮层——MICrONS

- **数据**：MICrONS Layer 2/3 v185.1（DOI `10.5281/zenodo.3710459`，CC-BY-4.0，334 节点 / 1,959 边——B1 报告已锁定）。MICrONS Basil 全图 2.15GB BossDB S3 备选。
- **许可**：**CC-BY-4.0**（Creative Commons Attribution 4.0，可再分发/再使用，需署名；status=open，embargo 无）。
- **数据规模**：75,000 神经元体内功能（microns-explorer.org / Nature 2025-04-09）。
- **FlyBrain 现状**：已有 `mammal_data/mouse_v1_l23/`（soma_subgraph_synapses_spines_v185.csv 274KB + soma_valence_v185.csv 30KB）；子图纯兴奋性（334e，34i 不在子图——B1 报告确认）。
- **获取难度：低**（Zenodo 公开）。

### 2.6 章鱼垂直叶（Octopus vulgaris）——Bidel 2023

- **论文**：Bidel et al., eLife 2023, 12:e84257，DOI `10.7554/elife.84257`。
- **许可**：**CC-BY-4.0**（crossref license 确认）。
- **数据**：accession `octopus_connectomes`（crossref is-supplemented-by 确认）。
- **范围**：**仅垂直叶（记忆获取网络），非全脑**——motif 抽取可用（局部回路），但覆盖面有限。
- **获取难度：低**（eLife 公开）。

### 2.7 鸟类 / 头足类其他 / 哺乳动物非 V1——**无真实 EM 连接组**

诚实标注（不夸大）：
- **鸟类**：无真实 EM 连接组数据集（仅综述/概念模式，如实标注）。
- **头足类（除章鱼垂直叶）**：章鱼臂/鱿鱼脑为 MRI/扩散成像（非突触级连接组），仅"全脑宏观连接"（bioRxiv 2025 DOI 10.1101/2025.05.28.656524，预印本，中可信度）——非 EM 突触级。
- **哺乳动物非 V1**：仅文献概念模式，无真实连接组数据。

---

## 3. 获取难度综合评估

| 物种 | 下载方式 | 工具链 | 难度 |
|---|---|---|---|
| MaleCNS | GCS `gs://lee-lab_brain-and-nerve-cord-fly-connectome/` | gsutil（需配置） | 中 |
| 果蝇幼虫 | Zenodo 直接 HTTP | 任意 | 低 |
| C.elegans | eLife 补充 + WormWiring | 任意 | 低 |
| 斑马鱼 | bioRxiv 公开 | 任意 | 低 |
| 小鼠 V1 | Zenodo 10.5281/zenodo.3710459 | 任意 | 低 |
| 章鱼垂直叶 | eLife 公开 | 任意 | 低 |

**综合**：除 MaleCNS（GCS 需 gsutil）外，全部低难度公开下载。

---

## 4. motif 抽取适合性

| 物种 | 规模 | 是否适合 motif 抽取 | 说明 |
|---|---|---|---|
| MaleCNS | 166,700 神经元 | ✅ 高 | 旗舰规模，FlyBrain 已整合 |
| 果蝇幼虫 | 3,016 神经元 / 548k 突触 | ✅ 高 | 完整小脑，已有数据 |
| C.elegans | 302 节点 / 19,608 边 | ✅ 高 | 已通过 PASS（AUC 1.00, kappa 0.95） |
| 斑马鱼 | 26,593 节点 / 42,640 边 | ✅ 中高 | PARTIAL（AUC 0.50），规模中 |
| 小鼠 V1 | 334 节点 / 1,959 边 | ✅ 中 | 子图纯兴奋性，B1 已锁 |
| 章鱼垂直叶 | 局部回路 | ✅ 中 | 记忆网络，覆盖有限 |

**结论**：最适合作为下一个锚定来源的候选排序——**斑马鱼幼虫（规模最大、真实数据，但 CC-BY-NC 商用受限）＞ 小鼠 V1（已 B1 锁定、CC-BY-4.0 无商用限制）＞ 章鱼垂直叶（真实但局部）**。鸟类与头足类其余无真实数据，不宜作锚定来源。

---

## 5. 风险与注意事项

1. **斑马鱼许可**：Petkova 2025 是 **CC-BY-NC-4.0（禁止商用）**——若 FlyBrain 商业化，需重新评估或获取替代源。
2. **文档事实错误**：FlyBrain `docs/arxiv_paper.md` 把 Petkova 2025 标为 "eLife"，实际是 **bioRxiv 预印本**。需修正文档（诚实披露，建议 FlyBrain 工程 Agent 后续修正）。
3. **章鱼垂直叶范围**：仅垂直叶，非全脑——作为"全脑锚定"不充分，仅局部回路。
4. **获取工具链**：MaleCNS 需 gsutil（GCS），其余低难度。
5. **许可再分发**：所有 CC-BY 类可再分发（需署名）；斑马鱼 CC-BY-NC 禁止商用；MaleCNS Data CC-BY / Code MIT。

---

## 6. 数据源索引（真实 URL / DOI）

- MaleCNS：https://male-cns.janelia.org ；GCS `gs://lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/`
- BANC：https://github.com/htem/BANC-project ；FAFB：Dorkenwald 2024 Nature DOI 10.1038/s41586-024-07558-y
- MANC：https://flyconnectome.com ；Hemibrain：Scheffer 2020 eLife
- 果蝇幼虫：DOI 10.1126/science.add9330；Zenodo https://doi.org/10.5281/zenodo.7473718 ；https://doi.org/10.5281/zenodo.7473710
- C.elegans：DOI 10.7554/eLife.47155；WormWiring（宿主 8 重建）
- 斑马鱼：DOI 10.1101/2025.06.10.658982（bioRxiv）
- 小鼠 V1：DOI 10.5281/zenodo.3710459（MICrONS v185.1）
- 章鱼垂直叶：DOI 10.7554/elife.84257（Bidel 2023）
- 头足类宏观：DOI 10.1101/2025.05.28.656524（bioRxiv，仅 MRI 宏观，非 EM）

---

> **归档**：本报告由蜂群agent（协助 FlyBrain P1）撰写，仅调研，未改动 FlyBrain 代码。配套许可矩阵见 `COMPLIANCE_LICENSE_MATRIX_2026-11-02.md`。
