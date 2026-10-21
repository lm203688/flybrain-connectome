# B 腿主线论文投稿前置任务清单 — 2026-10-19

> 目的：明确「补完 B 腿所需的全部任务」，完成后再投 B 腿（P-1 主线 + P-4 Xu 2026 短文）。
> 依据：`docs/SCI_VERDICT_2026-10-19.md` G-NOW-4 + §3 Q3。
> 优先级：**A 腿先行（P-3 → P-2，本周投 arXiv）；B 腿任务并行推进（2-3 周）**。

---

## 1. 任务列表

| # | 任务 | 预期工时 | 状态 |
|---|---|---|---|
| B-1 | **R6 跨 4 支 motif 保守性外部复现** | 10-15h | 🔴 TODO |
| B-2 | **R6 结果接入主线论文 §4.10** | 2h | 🔴 BLOCKED on B-1 |
| B-3 | **R6 结果接入 research_claims.json 预注册** | 1h | 🔴 BLOCKED on B-1 |
| B-4 | **S1 跨物种 PARTIAL → POSITIVE 升格判定** | 2h | 🔴 BLOCKED on B-1 |
| B-5 | **主线 §5.5 Limitations 收敛**（把"scale/lineage-dependent"边界写死） | 1h | 🟡 PARTIAL（已入 §5.5，等 B-1 后收敛） |
| B-6 | **P-4 Xu 2026 短文交叉引用 P-3** | 1h | 🟡 PARTIAL（等 P-3 arXiv ID） |
| B-7 | **B 腿全部数据/代码/引用跑 60/60 门禁** | 0.5h | 🟡 PARTIAL（等 B-1 数据） |
| B-8 | **主线 arxiv_paper.md 投 q-bio.NC + cs.LG** | 用户点击 | 🔴 BLOCKED on B-1..B-7 |
| B-9 | **P-4 短文投 q-bio.NC** | 用户点击 | 🔴 BLOCKED on B-6 |

**总计工时**：约 18-22h 核心工作 + 2 次用户 arXiv submit 点击。

---

## 2. B-1 R6 跨 4 支 motif 保守性外部复现 — 详细

**动机**：主线的核心科学主张是「真实连接组结构信号在生物拓扑层跨物种保守」。当前只有 MaleCNS + C. elegans 两个真数据点，且 larva / zebrafish 为 PARTIAL。要冲击 q-bio.NC 主刊（Nature Communications / Cell Systems / Current Biology 类），R6 必须显示「同一组 motif 在至少 4 个进化支上保守」。

**当前基线**：
- 内部合成族：5/5 PASS（PR-3 v2）
- 外部：*C. elegans*（扁形动物）PASS AUC 1.00；larva / zebrafish（昆虫幼虫 / 脊椎动物）PARTIAL AUC 0.50

**候选跨 4 支外部连接组**（按进化距离排序）：
1. **C. elegans 成虫**（扁形动物）— 已 PASS，可作 baseline
2. **Homo sapiens cortical column**（哺乳动物）— Zeiser / Wang 2025 类
3. **Mus musculus barrel cortex**（哺乳动物）— Kwon 2015 类
4. **Danio rerio zebrafish whole brain**（脊椎动物）— Petkova 2025 部分已加载，需扩到全脑
5. **Drosophila adult CNS**（昆虫成虫）— 已有 MaleCNS 成虫作 baseline

**建议方案**（挑 4 个真已发表、可离线加载的）：
- 用 **C. elegans 成虫 + Drosophila adult + zebrafish whole brain + 一个哺乳动物局部连接组**（Homo sapiens 或 Mus musculus 的公开子图）
- 每个连接组跑一遍 PR-3 v2 5-族扫描 + PR-1 前置预测 + PR-2 干预
- 目标：至少 3/4 达 AUC ≥ 0.7（PASS）才算 R6 完成

**风险**：
- 哺乳动物连接组公开子图数量少且规模差异大
- 部分连接组无 license 允许再分发，只能跑在本地
- 4 支复现若仍 PARTIAL，说明「scale/lineage-dependent」是**真的边界**，R6 无法升格，主线只能作 PARTIAL 主张投 SCIE（Bioinformatics / PLoS Comput Biol 而非 Nature 系）

**判定门槛**（预注册）：
- 4 支中 ≥ 3 支 AUC ≥ 0.7 → R6 PASS → B 腿可冲击主刊
- 4 支中 2-3 支 AUC ∈ [0.5, 0.7) → R6 PARTIAL → 主线投 SCIE 而非主刊
- 4 支中 ≤ 1 支 AUC ≥ 0.7 → R6 FAIL → 主线降级为方法学短文

---

## 3. 后续动作（A 腿先行）

**用户本周可做（0 元）**：
1. 打开 `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` §4 checklist
2. 依次提交：P-3 → P-2（stat.ME 主，cs.LG / q-bio.NC 交叉）
3. 拿到 arXiv IDs 后回填本文件 §5.5 和 `docs/PR2B_PREEXECUTION_REJECTION_PAPER.md` References

**用户 B 腿任务并行推进**：
- B-1 需下载/接入 3-4 个外部连接组数据源
- 预计 2-3 周内完成 → 主线投稿窗口：2026-11-12 之后

---

## 4. 相关脚本

- `scripts/pr3_external_reproduction.py`（新，需在 B-1 中开发）
- `scripts/s1_external_validation.py`（现有，可扩展到 R6）
- `scripts/check_pr_s1.py`（Gate 62，需在 B-3 中扩展到 R6）

---

## 5. 判定门槛预注册（B-1 提交前锁定）

```
H_R6: 4 支外部连接组中，同一组 motif（inhibitory_hub, reservoir_smallworld,
     recurrent_feedback）在 ≥ 3 支上达 AUC ≥ 0.7 且 kappa ≥ 0.5
判定:
  PASS  → 主线 §4.10 升格为正性主张，可冲击主刊
  PARTIAL (2-3 支) → 主线维持 PARTIAL 边界，投 SCIE
  FAIL (≤1 支)    → 主线降级为方法学短文
置换检验: 每支 1000 次标签置换，双尾 p
```
