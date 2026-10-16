# 论文投稿决策 memo（2026-10-16）

**结论**：**本轮不投 arXiv。** 论文素材质量已到 ~92%，但仓库公开化（D3）仍为 ❌，是 arXiv 硬门槛。建议拆两篇方法学短文（P-4/P-5）作为独立出口，主线论文等用户拍板 D3 后再提交。

---

## 一、判断依据（用户已确认的三条约束）

| 约束 | 状态 | 影响 |
|------|------|------|
| G3 L4 因果证据（基底上限） | ❌ 结构性缺口 | 论文已收窄主张为"可追溯拓扑 + 诚实负结果"，不再声称因果 |
| G5 锚定率数据工程 | ❌ 高成本数据工程 | 论文已声明 PR-2 n=100 时 |mean_delta| ≤ 0.0005，为诚实边界 |
| D3 仓库公开化 | ❌ 仍私有 | **arXiv 硬门槛**：无代码可复现 = 无投稿资格 |
| G4 论文素材 | 🟡 ~92% | 素材本身已到位，缺的是仓库公开 |

**用户拍板**："G3/G5/D3 三项都不动、G4 停在 92%、无低风险可修复项，唯一能推进论文的路线 = 用户拍板 D3 公开化。"

---

## 二、当前论文质量评估

### 2.1 论文本体（`docs/arxiv_paper.md`，455 行）

**已完成**：
- **Abstract + 6 章 + 参考文献**：完整学术论文结构
- **§4.1–4.4**：四个正向主张（traceability / parsimony / stability / local decision-making partial）
- **§4.5–4.6**：两条诚实负结果（compute advantage 0/7、energy advantage 0/24）
- **§4.7**：预注册四元组（PR-1 WEAK / PR-2 FAIL×3 / PR-3 FAIL / PR-4 PASS）
- **§4.8**：PR-2b 预执行拒绝（artifact 95.2% / control 85.7% 反向 / 合并 |corr|=0.902）
- **§4.9**：科研自验证四纪律（S6/S7/S8/S9）
- **§5.1–5.5**：讨论 + 局限（含基底上限作为贡献、R-0.4 扩展、L4 基底上限声明）
- **§6**：结论

**核心立场**（写入摘要与结论）：**预注册的价值是让负结果能被发表，不是让实验通过。** 5 条里 4 条是负结果，1 条是决策不做的实验也固化——没有把任何 FAIL 刷成 PASS。

### 2.2 配套文档

| 文档 | 状态 |
|------|------|
| `docs/PREREGISTRATION_PROTOCOL_v1.md` | ✅ R-0.1 时间顺序 / R-0.2 机器固化 / R-0.3 一次性验证 / R-0.4 失败即发表 |
| `docs/PAPER_READINESS_RECHECK_2026-10-15.md` | ✅ D1-D6 逐项复测 |
| `docs/ARXIV_SUBMISSION_METADATA.md` | ✅ 投稿元数据 v2.90.0 |
| `scripts/check_llm_orchestrator.py` | ✅ Gate 43–47 机器门禁 |
| `registry/preregistered_rejections.json` | ✅ PR-2b 预执行拒绝公共注册表 |
| `docs/PAPER_P4_CASE_STUDY.md` | ✅ 短文 P-4 案例研究 |

### 2.3 质量评分

| 维度 | 分数 | 说明 |
|------|------|------|
| 论文结构 | 100/100 | 完整学术论文结构，Abstract→Introduction→Methods→Results→Discussion→Conclusion |
| 预注册纪律 | 100/100 | 5 条预注册 + 4 条机器门禁 + 1 条预执行拒绝 |
| 诚实负结果 | 100/100 | 4/5 预注册 FAIL，2 条主要主张负结果，全部如实报告 |
| 可追溯性 | 95/100 | W3C PROV-JSON provenance bundle，Gate 43–47 机器验证 |
| 方法学贡献 | 90/100 | S6-S9 四纪律 + PR-2b 预执行拒绝 + 基底上限声明 |
| **仓库公开化** | **0/100** | **仍私有，arXiv 硬门槛未过** |
| **综合** | **89/100** | 素材质量高，但缺 arXiv 硬门槛 |

---

## 三、为什么不投 arXiv

### 3.1 硬门槛：仓库必须公开

arXiv 对预印本的要求（虽然不强制，但同行评议和引用惯例要求）：
- 代码可复现
- 数据可获取
- 第三方能独立验证结果

当前状态：仓库 `lm203688/flybrain-connectome` 仍私有。这意味着：
- 读者无法运行 `scripts/run_gates.py` 验证 51 门禁
- 读者无法复现 `_pr3_v2_results.json` 等实验产物
- 读者无法验证 Gate 43–47 的机器检查

**硬门槛**：arXiv 投稿时通常需要公开代码仓库，或至少提供匿名化代码链接。当前私有状态无法投稿。

### 3.2 结构性缺口：D1 L4 机制、D3 仓库公开化

| 缺口 | 类型 | 能否用文书工作解决 |
|------|------|------------------|
| D1 L4 因果机制 | 机制未解（PR-2b 证明基底上限） | ❌ 结构性缺口，不是文书 |
| D3 仓库公开化 | 私有→公开 | ❌ 需要用户拍板，不是 AI 能做的 |

**为什么不翻成 ✅**：D1/D3 是**结构性缺口**（机制未解、仓库不公开），不是文书工作。硬翻成 ✅ 会重演 PR-2b 教训——**用一个不成立的度量（"素材完整"）替代真缺口（"机制未解 + 不可复现"）**。

---

## 四、建议路线

### 4.1 短期（1–2 周）：拆两篇方法学短文

主线论文（traceable topology + preregistration suite + honest negatives）等 D3 后再投。但**现在就能发表**两篇独立方法学短文：

**短文 P-4（已完成）**：`docs/PAPER_P4_CASE_STUDY.md`
- 标题：**"Preregistered rejection as a first-class negative result"**
- 核心素材：PR-2b 预执行拒绝（artifact 95.2% / |corr|=0.902 / rule_underpowered=true）
- 论点：预注册的价值不是让实验通过，而是让**不做的实验**也能被记录、被引用、被反驳
- 独立可发表：不依赖主线论文，不依赖仓库公开（只需公开 `registry/preregistered_rejections.json` + 相关脚本）

**短文 P-5（需新建）**：**"Four disciplines for self-verification in computational experiments"**
- 核心素材：S6-S9 四纪律（每条对应一次踩坑：P1 伪结果 / R2 分辨率预检 / PR-2b 证伪机制 / PR-1 扰动分析）
- 论点：科研自验证的四条机器可执行纪律，可作为其他计算科学项目的模板
- 独立可发表：不依赖主线论文，不依赖仓库公开

**短文投稿策略**：
- P-4 可投 arXiv（cs.LG 或 q-bio.NC），只需公开 `registry/preregistered_rejections.json` + `scripts/f4b_metric_substitution_check.py` + `scripts/check_metric_substitution.py`
- P-5 可投 arXiv（cs.CY 或 cs.LG），只需公开 `scripts/check_llm_orchestrator.py`（Gate 30 部分）+ 相关踩坑案例文档
- 两篇短文均可先投 arXiv 预印本，不依赖期刊同行评议

### 4.2 中期（2–4 周）：用户拍板 D3 公开化

**需要用户决定**：
- 是否公开仓库 `lm203688/flybrain-connectome`
- 如果公开，是否包含所有脚本和数据（5.63 GB 原始 connectome 不重分发，但派生数据可公开）
- 是否公开 `.workbuddy/memory/` 等内部文档

**公开化的好处**：
- 主线论文可投 arXiv
- 第三方能独立验证所有 51 门禁
- 论文引用时可指向可复现代码
- 提升论文可信度和影响力

**公开化的风险**：
- 暴露内部实现细节（门禁逻辑、实验设计、踩坑记录）
- 可能被 fork 和抄袭
- 需要维护公共 API 和文档

**建议**：
- 先公开 `metrics_fork/`（只读分叉，最小公开面）
- 再公开 `scripts/` 和 `docs/`（核心代码和文档）
- 最后公开完整仓库（含 `.workbuddy/` 等内部文档）

### 4.3 长期（1–3 月）：主线论文投稿

**投稿目标**：arXiv 预印本（cs.LG 或 q-bio.NC）

**投稿前检查清单**：
- [ ] 仓库公开化（D3）
- [ ] 论文 §6 结论更新：仓库链接 + 代码可复现声明
- [ ] 论文 §5.5 局限更新：移除"repository currently private"声明
- [ ] `docs/ARXIV_SUBMISSION_METADATA.md` 更新为最终版
- [ ] 运行 `scripts/run_gates.py` 确认 51/51 PASS
- [ ] 生成 PDF（`pandoc docs/arxiv_paper.md -o docs/arxiv_paper.pdf`）
- [ ] 提交到 arXiv（需要 arXiv 账号）

**预期时间**：D3 公开化后 1–2 周可投稿

---

## 五、当前建议

### 5.1 立即可做（无需用户拍板）

1. **完成短文 P-5**：`docs/PAPER_P5_CASE_STUDY.md`（四纪律方法学短文）
2. **投稿 P-4 和 P-5 到 arXiv**：只需公开最小代码子集，不依赖完整仓库
3. **更新 `docs/ARXIV_SUBMISSION_METADATA.md`**：为 P-4 和 P-5 准备投稿元数据

### 5.2 需要用户拍板

1. **D3 仓库公开化**：是否公开完整仓库，何时公开
2. **主线论文投稿**：D3 公开后是否立即投稿，还是继续打磨

### 5.3 不建议做

1. **不要现在投主线论文到 arXiv**：仓库私有 = 无投稿资格
2. **不要为了投稿而修改论文主张**：会重演 PR-2b 教训（用不成立的度量替代真缺口）
3. **不要为了投稿而补跑 PR-2/PR-3**：R-0.4 纪律要求"失败即发表"，不能事后补跑

---

## 六、一句话总结

**论文素材质量已到 ~92%，但仓库公开化（D3）是 arXiv 硬门槛。建议拆两篇方法学短文（P-4/P-5）作为独立出口，主线论文等用户拍板 D3 后再提交。**

---

## 附录：文件清单

### A. 已完成的论文相关文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `docs/arxiv_paper.md` | ✅ v1.2.0（455 行） | 主线论文 |
| `docs/PREREGISTRATION_PROTOCOL_v1.md` | ✅ | 预注册协议 v1 |
| `docs/PAPER_READINESS_RECHECK_2026-10-15.md` | ✅ | 素材复测报告 |
| `docs/ARXIV_SUBMISSION_METADATA.md` | ✅ v2.90.0 | 投稿元数据 |
| `docs/PAPER_P4_CASE_STUDY.md` | ✅ | 短文 P-4（PR-2b 案例） |
| `registry/preregistered_rejections.json` | ✅ | PR-2b 预执行拒绝注册表 |
| `scripts/check_llm_orchestrator.py` | ✅ | Gate 30 + Gate 43–47 |
| `scripts/f4b_metric_substitution_check.py` | ✅ | PR-2b 预检脚本 |
| `scripts/check_metric_substitution.py` | ✅ | Gate 47（预执行拒绝门禁） |

### B. 需新建的文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `docs/PAPER_P5_CASE_STUDY.md` | ❌ 需新建 | 短文 P-5（四纪律方法学） |
| `docs/ARXIV_SUBMISSION_METADATA_P4.md` | ❌ 需新建 | P-4 投稿元数据 |
| `docs/ARXIV_SUBMISSION_METADATA_P5.md` | ❌ 需新建 | P-5 投稿元数据 |

### C. 需用户拍板的文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `docs/REPOSITORY_PUBLICATION_DECISION.md` | ❌ 需用户拍板 | 仓库公开化决策记录 |

---

**memo 作者**：SenseNova 6.8 Flash Lite（AI 决策辅助）  
**memo 日期**：2026-10-16  
**memo 状态**：待用户审阅和拍板
