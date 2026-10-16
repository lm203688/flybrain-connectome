# HYPOTHESIS TEST PROTOCOL v1 — 假设检验执行层规范

- 版本：v1.0 · 2026-10-11
- 上游来源：`docs/AUTOSCIENTISTS_FUSION_2026-10-11.md` 第三层（Gate 30 四纪律）
- 定位：把「假设」变成可执行、可复现、可判定的实验契约
- 使用方式：每个科研产出单元（论文/结论/机制说）**必须**附一份 Hypothesis Spec JSON

---

## 为什么需要这一层

Gate 30 已经管住「假说不成立时能不能发出去」（S6/S7/S8/S9 四纪律），但仍缺**前置契约**：
一个假设在跑实验前有没有被清晰写出来？变量范围、判据公式、对照组是否可得分、机制证伪
的判定边界，全在人脑里——这正是 P1 伪结果（motif_family 一个任务类伪造 +33.4pp 整体效应）
得以过关的原因。

**本层解决**：假设不写清楚就不给跑，机制证伪不结构化就不给发。

---

## 1. Hypothesis Spec 规范（9 字段，JSON Schema）

每个假设必须写成一份 `hypothesis_*.spec.json`，包含且**必须**含以下 9 字段：

```json
{
  "hypothesis_id": "H-XXX-YYYYMMDD",
  "statement": "一句话陈述（含方向与可证伪点）",
  "variables": {
    "independent": ["变量名，含取值范围"],
    "dependent": ["变量名，含量纲"],
    "confounders": ["已识别混杂变量"]
  },
  "prediction": {
    "direction": "positive|negative|monotonic|u_shape",
    "magnitude": "预估区间",
    "confidence": "high|medium|low"
  },
  "validation_criteria": {
    "pass_threshold": "数值 + 公式引用",
    "fail_threshold": "数值 + 公式引用",
    "metric_source": "计算函数或数据源"
  },
  "control_conditions": {
    "description": "对照组定义",
    "scoreability_check": "对照组在每组任务/子集是否可得分"
  },
  "pre_registration": {
    "registered_at": "ISO 时间戳",
    "lock_commit": "git commit hash（冻结后不允许改）"
  },
  "falsification_boundary": {
    "what_counts_as_falsification": "结构化的失败条件",
    "what_does_not": "不算失败的情形（避免过度证伪）"
  }
}
```

### 字段强约束

| 字段 | 硬要求 | 违规后果 |
|---|---|---|
| `statement` | 必须含「若 X 则 Y」结构，含可证伪点 | 拒绝 |
| `variables.independent` | 每个必须给取值范围或枚举 | 拒绝 |
| `variables.dependent` | 每个必须给量纲或计算方式 | 拒绝 |
| `prediction.confidence` | 必填，避免事后合理化 | 拒绝 |
| `validation_criteria.pass_threshold` | 必须引用公式/函数，不接受「显著提升」类描述 | 拒绝 |
| `control_conditions.scoreability_check` | **S6 强制**——若某任务类对照组构造上不可得分，必须显式标注并声明剔除或分层报告 | 拒绝 |
| `pre_registration.lock_commit` | 冻结后改动需 append 版次，不允许就地修改 | 拒绝 |
| `falsification_boundary.what_counts_as_falsification` | **S8 强制**——必须是结构化列表，不能一句「不成立」 | 拒绝 |

---

## 2. 判据矩阵（4 种判定条件 × 3 种结果）

假设跑出结果后，按此矩阵归档：

| 判定条件 | 结果标签 | 处置 |
|---|---|---|
| 显著（p < 0.05 + effect size 达阈值） | `SUPPORTED` | 主文档可引用；仍要求 falsification_boundary |
| 不显著 | `NULL` | 报告为「未检测到效应」，不得表述为「效应不存在」 |
| 反向显著 | `CONTRADICTED` | **必须触发机制证伪记录**（S8），不得静默丢弃 |

**关键纪律**：`NULL` 与 `CONTRADICTED` 都是产出，不是失败。P1 的错误就是把 `CONTRADICTED`
（motif_family 层 CONTRA + reachability 层 CONTRA + hub 层 NULL）包装成"方向反转、推翻 0/7"。

---

## 3. 三阶段生命周期状态机

```
DRAFT ──── 预注册 (pre-registration lock) ────▶ REGISTERED
  │                                                │
  │ 违反字段强约束                                  │ 实验启动
  │  → 拒绝                                        ▼
  │                                        RUNNING
  │                                                │
  │  实验完成                                      │ 结果产生
  ▼                                                ▼
INVALIDATED                              VERDICTED {SUPPORTED | NULL | CONTRADICTED}
  (S8 机制证伪触发)                                │
                                                  ▼
                                            ARCHIVED
```

**关键转移条件**：
- `DRAFT → REGISTERED`：9 字段全部合规 + commit 冻结
- `REGISTERED → RUNNING`：允许，且 running 阶段**不允许**改 `pre_registration` 或 `validation_criteria`
- `RUNNING → VERDICTED`：结果按判据矩阵归档；`CONTRADICTED` 必须同时产出 `falsified_mechanisms` 结构化列表
- `VERDICTED → INVALIDATED`：后续发现对照组不可得分、混杂未控、机制声明过宽——回退并追加「复核与修正」章节（**不允许删原报告**）

---

## 4. 与 Gate 30 四纪律的接口映射

| Gate 30 纪律 | 本层承载 |
|---|---|
| **S6** 对照组可得分性 | `control_conditions.scoreability_check` 字段强制 |
| **S7** 分辨率预检 | `variables.independent` 取值范围 + `validation_criteria.metric_source` 必须给出分辨率上限 |
| **S8** 机制证伪即产出 | `falsification_boundary` + `VERDICTED(CONTRADICTED)` 触发的 `falsified_mechanisms` |
| **S9** 扰动分析优于相关性 | `prediction.confidence` 低 + `falsification_boundary` 边界声明；相关 R² < 0.05 时必须附扰动数据 |

---

## 5. 落地清单（分三档，本次交付 A 档）

### A 档（✅ 已落地）
- ✅ 本文档 `HYPOTHESIS_TEST_PROTOCOL_v1.md`
- ✅ 5 个 Spec 模板文件：
  - `hypothesis_template.blank.json` — 全空 9 字段
  - `hypothesis_template.r1_expansion.json` — R1 扩样 N≥100 + 机制检验（Phase 1 主实验）
  - `hypothesis_template.r2_density.json` — R2 密度扫描（含 S7 分辨率上限预检）
  - `hypothesis_template.r4_sensitivity.json` — R4 敏感性边界（含 remove 边界 0.1）
  - `hypothesis_template.p1_revised.json` — **P1 修正实验**：LLM 编排基底 + 按 task_type 分层 + motif_family 对照组修正
- ✅ CHANGELOG v2.65.0
- ✅ 版本号 5 文件已同步
- ✅ Gate 1–4 冒烟全过

### B 档（待做，Gate 31 候选）
- ⬜ 新增 `scripts/checks/check_hypothesis_specs.py` 门禁
- ⬜ 校验：
  - 所有 `hypothesis_*.spec.json` 是否含 9 字段
  - 若 `pre_registration.lock_commit` 有值，该 commit 是否真实存在
  - 若 `verdict = CONTRADICTED`，`falsified_mechanisms` 是否含五字段（mechanism / direction / boundary / data_source / confidence_of_boundary）
  - `control_conditions.scoreability_check` 不能为空且必须逐任务类标注
- ⬜ 加 2 个注入：① 缺字段 ② CONTRADICTED 缺 falsified_mechanisms
- ⬜ 加 1 个注入：`pre_registration.lock_commit` 篡改检测
- ⬜ 注册进 `run_gates.py`；同步 README / mcp_setup / Gate 9 count

### C 档（远期，需评估）
- ⬜ CI 自动跑：任何新 `hypothesis_*.spec.json` 加入时自动触发 B 档门禁
- ⬜ 与 AutoScientists 类自动化实验框架打通——S6 纪律落地后再引入
- ⬜ Spec 版本 diff 视图（v1 vs v2 修改痕迹）

---

## 6. 首个实战案例：P1 修正实验

参见 `hypothesis_p1_revised.spec.json`。它直接暴露了旧 P1 的所有问题：

- **旧 P1 的假设陈述**：「结构蓝图在 ESN 基底上优于随机」（**基底错了**，AdaptOrch 已证结构价值在 LLM 编排）
- **旧 P1 的对照组**：random 组 33 个 task_type 中 motif_family 全部构造性不可得分（`llm_tasks.py:272/339`）
- **旧 P1 的判据**：整体准确率差值（**未按任务类拆分**，+0.973 motif_family 效应吞掉 hub 层 -0.070 真信号）
- **修正后**：
  - 基底：LLM 编排（4 拓扑）
  - 判据：按 task_type 分层的准确率差值 + 每任务类独立显著性
  - 对照修正：motif_family 组 random 组剔除或单独报告
  - `falsification_boundary.what_counts_as_falsification`：≥3 任务类显著负向 + 综合效应 < 0

**教训**：Gate 30 的 S6 已经写进了纪律清单，但没有 Spec 契约时，纪律只能靠「事后审计」补——
审计本身又漏了（P1 报告 10-05 落笔时无人问「motif_family 对照组能否得分」）。
**前置契约是最后一道防线**。
