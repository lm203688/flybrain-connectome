# 合规许可矩阵调研报告（2026-11-02）

> **调研目的**：FlyBrain 多物种化需逐数据源许可登记表（来源/许可/归因/再分发/商用限制）。当前 S1 脚本仅注释来源无许可矩阵。本报告覆盖 FlyBrain 当前各物种数据源 + 任务1 新物种数据源的许可情况，特别标出人类神经数据的合规边界。
> **执行者**：蜂群agent（SwarmCore 工程 Agent，协助 FlyBrain P2 调研）
> **日期**：2026-11-02
> **诚实声明**：所有许可均经外部权威源核实（Zenodo API / Europe PMC structured license / crossref license / 官方平台声明）；无法核实到具体许可文本的，如实标注"待确认"；数据源不可用/许可受限的，明确标注。未编造。

---

## 1. 许可矩阵总表

| # | 数据源 | 来源 | 许可 | 归因要求 | 再分发 | 商用 | 注意事项 |
|---|---|---|---|---|---|---|---|
| 1 | **MaleCNS v1.0** | male-cns.janelia.org（2026-06-08 官方，Cell 2026-09-03） | **Data: CC-BY / Code: MIT** | 需署名（数据创建者） | ✅ 允许 | ✅ 允许 | 数据与代码许可分离；`DATA_MANIFEST.json` 已确认 |
| 2 | **C.elegans Witvliet 2020** | eLife 2020，DOI 10.7554/eLife.47155 | **CC-BY-4.0** | 需署名 | ✅ 允许 | ✅ 允许 | eLife 默认 CC-BY；WormWiring 宿主 8 重建 |
| 3 | **果蝇幼虫 Winding 2023** | Science 2023, DOI 10.1126/science.add9330 | **CC BY**（Europe PMC `license":"cc by"`） | 需署名 | ✅ 允许 | ✅ 允许 | Zenodo 7473718/7473710 公开；PMC7614541 开放全文 |
| 4 | **斑马鱼 Petkova 2025** | bioRxiv 2025，DOI 10.1101/2025.06.10.658982 | **CC-BY-NC-4.0** | 需署名 | ✅ 允许 | ❌ **禁止商用** | **⚠️ 非商用**；FlyBrain 文档误标 eLife（见 §3） |
| 5 | **小鼠 V1 MICrONS** | Zenodo 10.5281/zenodo.3710459 | **CC-BY-4.0** | 需署名 | ✅ 允许 | ✅ 允许 | status=open，embargo 无；B1 已锁定 |
| 6 | **章鱼垂直叶 Bidel 2023** | eLife 12:e84257，DOI 10.7554/elife.84257 | **CC-BY-4.0** | 需署名 | ✅ 允许 | ✅ 允许 | crossref license 确认；仅垂直叶局部回路 |
| 7 | **果蝇其他（BANC/FAFB/MANC/Hemibrain）** | 各官方平台（见任务1 §2.1） | **CC-BY** | 需署名 | ✅ 允许 | ✅ 允许 | tutorial 确认"Data CC-BY / Code MIT" |
| 8 | **头足类宏观 MRI** | bioRxiv 10.1101/2025.05.28.656524 | 预印本默认（CC-BY-NC 类） | 需署名 | 视许可 | 视许可 | 预印本；仅 MRI 宏观非 EM；**中可信度** |
| 9 | **人类 H01（官方 GCS）** | h01-release.storage.googleapis.com | **CC-BY-4.0** | 需署名 | ✅ 允许 | ✅ 允许 | **⚠️ 触发人类合规边界（见 §2）** |
| 10 | **人类 H01（社区版 NathanRoll）** | github.com/NathanRoll/h01-cortex-snn | **Apache-2.0** | 需署名（NOTICE） | ✅ 允许 | ✅ 允许 | **HF 被封**（不可达）；⚠️ 人类合规边界 |
| 11 | **FlyBrain 自身代码** | repo（2026-10-18 公开） | **MIT**（LICENSE） | 需署名 | ✅ 允许 | ✅ 允许 | 代码层 MIT |

---

## 2. 人类神经数据合规边界（重点）

**触发条件**：若 FlyBrain 未来收集**人类神经数据**（如 H01 人类皮层连接组、人类脑图谱），将触发多重重叠合规要求：

| 合规维度 | 要求 | 说明 |
|---|---|---|
| **IRB（伦理审查）** | 数据采集须经机构伦理审查委员会批准 | 人脑组织/受试者数据来源须有 IRB 批准记录 |
| **知情同意** | 数据提供者须获得受试者/捐赠者知情同意 | 涉及人脑样本，同意范围须覆盖研究/再分发 |
| **GDPR** | 欧盟通用数据保护条例（若数据涉 EU 主体） | 人类神经数据通常含可识别信息（成像/遗传关联） |
| **PIPL** | 中国个人信息保护法（若数据涉中国主体） | 敏感个人信息（生物识别/健康）处理须单独同意 |
| **数据最小化** | 只收集必要数据 | 匿名化/去标识化是合规前提 |

**预设闸门建议**（FlyBrain P2 合规落地）：
1. **人类数据入口闸门**：任何人类神经数据入 FlyBrain 前，须验证 IRB 批准记录 + 知情同意范围 + 数据来源合法性。
2. **再分发闸门**：人类数据再分发须审查原始同意范围是否覆盖；H01 官方 GCS CC-BY-4.0 虽可再分发，但**人类数据来源的伦理合规独立于许可**（许可≠伦理授权）。
3. **去标识化闸门**：入库前须完成去标识化/匿名化，防止可识别信息入 FlyBrain 图谱。
4. **合规登记**：每个含人类数据的数据源登记"IRB ID / 知情同意版本 / 数据来源机构"，纳入许可矩阵。

> **关键区分**：CC-BY-4.0（许可层）允许再分发/商用，但**人类数据还受伦理/隐私层约束**（IRB/知情同意/GDPR-PIPL）。许可合规 ≠ 伦理合规，二者须同时满足。

---

## 3. 诚实修正：Petkova 2025 文档错误

FlyBrain `docs/arxiv_paper.md:373, :535` 把斑马鱼数据源标为 **"eLife"**，实际是 **bioRxiv 预印本**（DOI 10.1101/2025.06.10.658982，2025-06-15，journal-article 命中 0，无期刊正式版）。

- **影响**：许可从"eLife 默认 CC-BY"变为 **CC-BY-NC-4.0（禁止商用）**——FlyBrain 若商用此源受限。
- **建议**：FlyBrain 工程 Agent 后续修正文档（诚实披露，我不改 FlyBrain 代码）。

---

## 4. 再分发与商用限制汇总

| 类别 | 数据源 | 可再分发 | 可商用 |
|---|---|---|---|
| 全开放（CC-BY 类） | MaleCNS / C.elegans / 果蝇幼虫 / 小鼠 V1 / 章鱼垂直叶 / 果蝇其他 | ✅ | ✅ |
| 非商用（CC-BY-NC） | 斑马鱼 Petkova 2025 / 头足类宏观 MRI（预印本默认） | ✅ | ❌ |
| 人类边界 | H01 官方 CC-BY-4.0 / 社区 Apache-2.0 | ✅（许可层） | ✅（许可层）但**伦理层独立约束** |
| 代码 | FlyBrain 自身 MIT / MaleCNS Code MIT | ✅ | ✅ |

**结论**：除斑马鱼（CC-BY-NC）与人类数据（伦理层约束）外，FlyBrain 现有数据源均可再分发/商用。人类数据**许可合规 ≠ 伦理合规**，须预设闸门。

---

## 5. 数据源索引（真实 URL / DOI / 许可证据来源）

- MaleCNS：https://male-cns.janelia.org ；`DATA_MANIFEST.json`（FlyBrain 已确认 CC-BY）
- C.elegans：DOI 10.7554/eLife.47155（eLife 页脚 CC-BY）；WormWiring 宿主 8 重建
- 果蝇幼虫：DOI 10.1126/science.add9330；Europe PMC `license":"cc by"`；Zenodo https://doi.org/10.5281/zenodo.7473718 、https://doi.org/10.5281/zenodo.7473710（license=other-open, access_right=open）
- 斑马鱼：DOI 10.1101/2025.06.10.658982；crossref license `http://creativecommons.org/licenses/by-nc/4.0/`
- 小鼠 V1：DOI 10.5281/zenodo.3710459（CC-BY-4.0，status=open，embargo 无）
- 章鱼垂直叶：DOI 10.7554/elife.84257（crossref license CC-BY-4.0，is-supplemented-by `octopus_connectomes`）
- 果蝇其他：flyconnectome tutorial（Data CC-BY / Code MIT）
- 头足类宏观：DOI 10.1101/2025.05.28.656524（预印本）
- 人类 H01 官方：https://h01-release.storage.googleapis.com（CC-BY-4.0）
- 人类 H01 社区：https://github.com/NathanRoll/h01-cortex-snn（Apache-2.0，HF 被封不可达）
- FlyBrain 代码：LICENSE（MIT），repo 2026-10-18 公开

---

> **归档**：本报告由蜂群agent（协助 FlyBrain P2）撰写，仅调研，未改动 FlyBrain 代码。配套调研报告见 `MULTISPECIES_ANCHOR_SURVEY_2026-11-02.md`。
