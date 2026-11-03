# 合规许可登记表（项目级落地 · 2026-11-03）

> **登记目的**：按任务书 P2-7 要求，为 FlyBrain 逐数据源建立许可登记表（来源/许可/归因/再分发/商用限制）+ 人类数据闸门预设。
> **依据**：蜂群agent 调研报告 `docs/COMPLIANCE_LICENSE_MATRIX_2026-11-02.md`（外部权威源核实，未编造）+ 本项目工程 Agent 独立核实的项目内现状。
> **执行者**：FlyBrain（DEV）
> **日期**：2026-11-03
> **诚实声明**：本登记表不新增任何许可判断，仅把已核实的许可事实登记为项目级依据；Petkova 2025 文档错误标注已在同日完成 5 处纠错（见 §4）。

---

## 1. 项目内数据资产许可现状（已核实）

| 资产 | 路径 | 许可 | 核实方式 | 商用 |
|---|---|---|---|---|
| MaleCNS v1.0 数据 | `male_cns/`（5.63GB） | **CC-BY** | `DATA_MANIFEST.json` dataset 字段 | ✅ 允许 |
| MaleCNS 代码 | 官方平台 | **MIT** | 官方声明 | ✅ 允许 |
| 线虫 C.elegans | `cel_data/`（188 行） | **CC-BY-4.0** | eLife DOI 10.7554/eLife.47155 | ✅ 允许 |
| 果蝇幼虫 | `larva_data/`（2,957 节点） | **CC-BY** | Science DOI 10.1126/science.add9330 | ✅ 允许 |
| 斑马鱼 Petkova 2025 | `zebrafish_data/paper_data/TEN_analysis/` | **CC-BY-NC-4.0**（禁止商用） | Crossref license `by-nc/4.0` | ❌ 禁止 |
| 小鼠 V1 MICrONS | `mammal_data/mouse_v1_l23/` | **CC-BY-4.0** | Zenodo DOI 10.5281/zenodo.3710459 | ✅ 允许 |
| 人类 H01 官方 | `connectome_sources/h01.py` | **CC-BY-4.0** | 官方 GCS | ✅ 允许（**伦理层独立约束**） |
| FlyBrain 自身代码 | `LICENSE` | **MIT** | LICENSE 文件 | ✅ 允许 |

**数据源代码层登记**（`connectome_sources/*.py` 已核实）：
- `microns.py` → `license="CC-BY"`（MICrONS Benson et al. 2025 public CAVE）
- `h01.py` → `license="CC-BY"`（官方 GCS）
- `zebrafish.py` → `license="CC-BY-NC"`（注释：`License is CC-BY-NC (non-commercial) per the foundation roadmap; that is stamped`）
- `zebrafish_profiles.json` → `license: CC-BY-NC`（1123 单元 / 142,882 突触）

---

## 2. 功能单元库许可登记缺口与处理

**现状**：`functional_units.json` 116 单元全部有 `provenance` 字段（class/basis/evidence_weight 等），但 provenance **无逐单元 license 字段**（主库缺口）。

**处理决定（诚实边界）**：
- **不在逐单元硬写 license**——116 单元多为 `curated-cross-species`（跨物种文献组合），`species_source` 覆盖 49 种物种组合（含人类/哺乳类/鱼类/头足类等），逐单元硬映射会把"数据源许可"与"文献引用许可"混淆，且多数单元的物种组合并非单一真实连接组来源。
- **在 `functional_units.json` 顶层增加 `license_registry`**：登记**数据源级**许可映射（数据源 → 许可 → 商用边界），供 provenance 引用。逐单元若需许可信息，从 `species_source` + `license_registry` 推导（不硬写、不虚构）。

**顶层 license_registry 内容**（已写入 `functional_units.json`，见同目录文件）：
- MaleCNS v1.0：CC-BY，商用允许
- C.elegans Witvliet 2020：CC-BY-4.0，商用允许
- Drosophila larva Winding 2023：CC-BY，商用允许
- zebrafish Petkova 2025：CC-BY-NC-4.0，**商用禁止**
- mouse V1 MICrONS：CC-BY-4.0，商用允许
- H01 official：CC-BY-4.0，商用允许（伦理层独立约束）

---

## 3. 人类神经数据合规闸门（预设）

> **触发条件**：仅当未来 FlyBrain 实际收集人类神经数据（如 H01 人类皮层连接组、人类脑图谱）时触发。当前项目**无人类神经数据源入账**（H01 社区版涉及人类数据但 HF 被封、不可达，未纳入资产）。

| 合规维度 | 闸门要求 | 状态 |
|---|---|---|
| **IRB 伦理审查** | 数据采集须经机构伦理审查委员会批准 | 预设（当前未触发） |
| **知情同意** | 数据提供者须获得受试者/捐赠者知情同意 | 预设（当前未触发） |
| **GDPR / PIPL** | 若涉 EU / 中国主体，须符合对应数据保护法 | 预设（当前未触发） |
| **去标识化** | 入库前须完成匿名化，防可识别信息入图谱 | 预设（当前未触发） |
| **合规登记** | 每个含人类数据的数据源登记 IRB ID / 同意版本 / 来源机构 | 预设（当前未触发） |

**关键区分**：CC-BY-4.0（许可层）允许再分发/商用，但**人类数据还受伦理/隐私层约束**（IRB/知情同意/GDPR-PIPL）。许可合规 ≠ 伦理合规，二者须同时满足。

---

## 4. Petkova 2025 纠错确认（已完成）

**权威事实**：DOI 10.1101/2025.06.10.658982 = Petkova, Mariela D. et al. 2025，**bioRxiv 预印本**（posted 2025-06-15），**CC-BY-NC-4.0**，标题 *A connectomic resource for neural cataloguing and circuit dissection of the larval zebrafish brain*。第一作者 M. D. Petkova（哈佛 MCB）。

**纠错 5 处（2026-11-03 完成）**：
1. `docs/arxiv_paper.md:373`（表）→ "Petkova et al. 2025, bioRxiv (preprint)"
2. `docs/arxiv_paper.md:534-535`（参考文献）→ bioRxiv preprint + DOI + CC-BY-NC-4.0
3. `docs/SCI_VERDICT_2026-10-19.md:35` → "bioRxiv preprint，CC-BY-NC-4.0，DOI 10.1101/2025.06.10.658982"
4. `docs/PAPER_P1_MAINLINE_MERGED.md:724` → "Petkova, M. D. et al. (2025)... bioRxiv preprint, DOI..., CC-BY-NC-4.0"
5. `docs/PAPER_P1_MAINLINE_MERGED.pandoc_input.md:736` → 同 4（pandoc 副本）

**已核实无需修改**：`FOUNDATION_ROADMAP.md`/`MULTISPECIES_ANCHOR_SURVEY_2026-11-02.md`/`SCI_READINESS_ASSESSMENT_2026-10-18.md` 等已正确标注 CC-BY-NC/bioRxiv。

---

## 5. 再分发与商用限制汇总

| 类别 | 数据源 | 可再分发 | 可商用 |
|---|---|---|---|
| 全开放（CC-BY 类） | MaleCNS / C.elegans / 果蝇幼虫 / 小鼠 V1 / H01 官方 | ✅ | ✅ |
| 非商用（CC-BY-NC） | 斑马鱼 Petkova 2025 | ✅ | ❌ |
| 人类边界 | H01 官方 CC-BY-4.0 | ✅（许可层） | ✅（许可层）但**伦理层独立约束** |
| 代码 | FlyBrain 自身 MIT / MaleCNS Code MIT | ✅ | ✅ |

**结论**：除斑马鱼（CC-BY-NC）与人类数据（伦理层约束）外，FlyBrain 现有数据源均可再分发/商用。斑马鱼数据若 FlyBrain 商业化需重新评估或获取替代源。

---

## 6. 来源索引

- MaleCNS：https://male-cns.janelia.org ；`DATA_MANIFEST.json`
- C.elegans：DOI 10.7554/eLife.47155（eLife 页脚 CC-BY）
- 果蝇幼虫：DOI 10.1126/science.add9330；Europe PMC `license":"cc by"`
- 斑马鱼：DOI 10.1101/2025.06.10.658982；Crossref license `http://creativecommons.org/licenses/by-nc/4.0/`
- 小鼠 V1：DOI 10.5281/zenodo.3710459（CC-BY-4.0）
- H01 官方：https://h01-release.storage.googleapis.com（CC-BY-4.0）
- FlyBrain 代码：LICENSE（MIT）
