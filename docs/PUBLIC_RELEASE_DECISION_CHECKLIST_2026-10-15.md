# D3 公开准备 — 决策清单（2026-10-15）

**来源**：`scripts/prep_public_release.py --dry-run` 输出（本轮复测）
**用途**：D3 公开化的**逐项拍板清单**。每一项必须由用户显式确认后再进入实际操作（脚本本身零副作用）。
**状态**：所有项均**未处置**（当前仅扫描，未改动任何文件、未推送任何清理）。

> ⚠️ **D3 是 SCI 硬门槛**：仓库不公开，P-1 主线论文与外部引用都无法真正验证。此清单是把「拍板」前置到用户手上，Agent 不代决策。

---

## 一、决策总览（先看这个）

| # | 类别 | 项数 | 推荐处置 | 用户成本 |
|---|---|---:|---|---|
| A | 敏感目录 | 5 | 4 项 keep（`.gitignore` 已覆盖）+ 1 项 clean | 无需操作 |
| B | 敏感文件 | 5 | 全部 keep（已在 `.gitignore` 或审计范围内） | 无需操作 |
| C | 私有声明残留 | 2 | 公开后再改文档口径（本轮**保持原声明**） | 需拍板 |
| D | Git 历史 | 全库 | 公开前**必须做**历史清洗（重写），否则 Tier-2 数据泄漏 | **需拍板 + 备份** |

**决策顺序**：先做 D（历史清洗）→ 再做 C（口径对齐）→ A/B 由 `.gitignore` 自动覆盖，无需操作。

---

## 二、A 类：敏感目录（5 项）

| # | 目录 | 大小 | `.gitignore` 状态 | 推荐 | 理由 |
|---|---|---:|---|---|---|
| A1 | `.workbuddy-ai/` | 3 files | ❌ **已追踪** | **需拍板**：keep 或迁移 | v2.67.0 起已被追踪（历史遗留）；本项目规范是 `.workbuddy/`（已 gitignore）。选项：(i) `git rm -r --cached .workbuddy-ai/` + 加 `.gitignore`；(ii) 保留作为「AI 侧工作日志」的公开痕迹。**推荐 (i)** |
| A2 | `archive/` | 16 MB / 1061 files | ✅ 已 ignore | keep | 已排除；`.gitignore:23` |
| A3 | `flybrain-tier2-backup-2026-09-22/` | 364 KB / 18 files | ✅ 已 ignore | keep | Tier-2 私有备份；`.gitignore` 规则 `flybrain-tier2-backup-*/`。**必须保留在 ignore**，绝不入库 |
| A4 | `generated_organisms/` | 12 KB / 1 file | ⚠️ **未在根 .gitignore** | clean 或加 ignore | `male_cns/generated_organisms/` 已 ignore，但根级 `generated_organisms/` 未覆盖。**推荐加根级 ignore**：`generated_organisms/` |
| A5 | `__pycache__/` | 1 file | ✅ 已 ignore | keep | `.gitignore:38` |

### A1 具体操作（如用户选择 keep → ignore）

```bash
git rm -r --cached .workbuddy-ai/
echo ".workbuddy-ai/" >> .gitignore
git add .gitignore
git commit -m "chore: move AI-side memory out of git tracking"
```

### A4 具体操作（推荐）

```bash
echo "generated_organisms/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore root-level generated_organisms/"
```

---

## 三、B 类：敏感文件（5 项）

| # | 文件 | 类型 | 推荐 | 理由 |
|---|---|---|---|---|
| B1 | `.secrets.baseline` | 加密基线 | keep | 项目 secret 扫描工具基线（truffleHog 标准产物），本身不含明文密钥 |
| B2 | `LICENSE-CLAUSE.md` | 法务条款 | keep | Tier-2 条款说明，公开仓库**应该**保留（说明数据层级制度） |
| B3 | `flybrain-connectome-core/LICENSE-CLAUSE.md` | Tier-2 副本 | clean | Tier-2 私有 repo 的条款副本，**不应出现在公共 repo 里**。目录整体已在 `.gitignore`（`flybrain-connectome-core/`），本文件应随目录排除 |
| B4 | `scripts/check_no_secrets.py` | 审计脚本 | keep | 项目自验证工具，公开有助于外部复现 secret 检查 |
| B5 | `scripts/__pycache__/check_no_secrets.cpython-313.pyc` | 编译缓存 | clean（自动） | `.gitignore:39` 已 ignore `__pycache__/`，此处出现是脚本扫描时的**已缓存副本**，不会入库 |

**说明**：B 类全部已被 `.gitignore` 或项目审计策略覆盖，**无需用户操作**，仅记录。

---

## 四、C 类：私有声明残留（2 项）

**问题**：`docs/arxiv_paper.md` 有 2 处声明仓库仍私有。公开后需要修改为「已公开」，否则论文与仓库状态矛盾。

| # | 位置 | 当前文本 | 公开后应改为 |
|---|---|---|---|
| C1 | `docs/arxiv_paper.md:5` | ``lm203688/flybrain-connectome` · MIT License (Tier-1 code; repository currently private, re-publicization planned)` | ``lm203688/flybrain-connectome` · MIT License (Tier-1 code; public)` |
| C2 | `docs/arxiv_paper.md:33` | `We present a method and a toolkit (currently private, re-publicization planned) that converts ...` | `We present a method and a toolkit that converts ...` |

### 当前状态与推荐

- **不公开前**：**保持原声明**（诚实反映当前状态；这是 SCI 硬门槛未通过时的合规写法）
- **公开后**：修改为「已公开」措辞，提交一个 `docs: align paper claims with public repo state` 提交
- **推荐**：先拍板 D3（公开或延迟），再决定 C1/C2 是否改。若 D3 不公开，C1/C2 **不改**

---

## 五、D 类：Git 历史清洗（**最关键**）

### 为什么必须做

D3 硬门槛不仅是「当前 tree 干净」，还包括**历史提交**里没有 Tier-2 私有数据。当前情况：

- 全库提交 100+ 次；历史里可能有：
  - **Tier-2 数据快照**（`flybrain-tier2-backup-*` 目录，虽当前 ignore，但**历史提交里可能包含**）
  - **早期 API key / 私有配置**（若 `.gitignore` 规则后加，早期提交可能残留）
  - **archive/ 目录早期内容**（虽当前 ignore，但历史可能已包含）
  - **用户级 memory 快照**（`.workbuddy-ai/memory/` v2.67.0 起已追踪）

### 判定：是否**必须**重写历史？

**判定标准**：如果任一 Tier-2 / secret / 私有数据在**任一历史提交**中可检出，则必须重写。

### 建议排查命令（用户手工执行，不要 Agent 代跑）

```bash
# 1. 扫描历史中的 secrets
git log --all --oneline -- scripts/check_no_secrets.py  # 是否曾改过检查规则？
"gh secret-tool scan" 2>/dev/null || true               # 若有 gh secret-tool

# 2. 检查历史中 Tier-2 数据是否曾出现
git log --all --diff-filter=A --name-only -- 'flybrain-tier2-backup-*' 'flybrain-connectome-core/**' | head -30

# 3. 检查 archive/ 早期内容
git log --all --diff-filter=A --name-only -- 'archive/*' | head -30

# 4. 检查 memory 目录历史
git log --all --oneline -- '.workbuddy-ai/*' '.workbuddy/*' | head -20
```

### 处置选项（用户拍板）

| 选项 | 说明 | 风险 | 成本 |
|---|---|---|---|
| **D-i 不重写** | 假设历史干净，直接公开 | 若历史含敏感数据 = **不可逆泄露** | 0 |
| **D-ii 局部重写** | 用 `git filter-branch` 或 `filter-repo` 只删特定 path（如 `.workbuddy-ai/`） | 中等（需备份 + 全员 rebase） | 1–2 小时 |
| **D-iii 全量重写** | 用 `git filter-repo` 从头重建历史，只保留 Tier-1 代码 | 高（所有分支 force-push） | 半天 + 备份 |
| **D-iv 延迟公开** | 不重写，继续私有；等 arXiv 收到回复后再定 | 与「SCI 硬门槛」目标冲突 | 0 |

**推荐**：**D-ii**（局部重写 `.workbuddy-ai/` + 抽查 Tier-2 数据）→ 用户先跑上表 4 条排查命令 → 根据结果决定 D-i / D-ii / D-iii。

### 前置备份（无论哪个选项）

```bash
# 在动手前必备份（Tier-2 数据不可再生）
robocopy /E /COPYALL . "..\flybrain-backup-$(date +%Y%m%d-%H%M%S)"
# 或
git bundle create flybrain-$(date +%Y%m%d).bundle --all
```

---

## 六、推荐执行顺序（用户拍板后）

```
Step 1 · 决定 D 选项（历史处置）
        └─ D-i   直接跳到 Step 3
        └─ D-ii  跑 4 条排查 → filter-branch/filter-repo → force-push
        └─ D-iii 全量重建 → force-push（最安全但成本高）
        └─ D-iv  停止本次公开准备

Step 2 · A1 决策（.workbuddy-ai 是否 remove from index）
        └─ 若 D-ii/D-iii：与历史清洗合并
        └─ 若 D-i：`git rm -r --cached .workbuddy-ai/` + ignore

Step 3 · A4 决策（generated_organisms 加 ignore）
        └─ 简单：加一行 .gitignore + commit

Step 4 · C1/C2 决策（文档口径）
        └─ 若已公开：改 2 处 arxiv_paper.md
        └─ 若仍私有：保持

Step 5 · 最终确认
        └─ `git status --short` 应全空
        └─ `scripts/prep_public_release.py --dry-run` 输出敏感目录 ≤ 2 项
        └─ 提交 `docs: D3 public release finalized`
```

---

## 七、Agent 已就绪 / 用户待决策

| 项 | 状态 |
|---|---|
| 扫描脚本 `prep_public_release.py` | ✅ 落地（v2.82.0），dry-run 零副作用 |
| 本决策清单 | ✅ 落地（本文件） |
| A1 决策 | ⏳ 用户拍板（推荐：keep → ignore） |
| A4 决策 | ⏳ 用户拍板（推荐：加根级 ignore） |
| B 类 | ✅ 已 gitignore 覆盖 |
| C1/C2 决策 | ⏳ 依赖 D3 拍板 |
| D 决策（历史清洗） | ⏳ **最关键**，用户拍板 |
| 备份 | ⏳ 用户执行（Tier-2 不可再生） |
| 公开操作 | ⏳ 用户执行（`gh repo edit --visibility public`） |

**Agent 本轮边界**：所有需要「删除用户数据」「重写 git 历史」「修改论文口径」的动作**均不代做**——这些是不可逆操作，必须由用户显式确认后手动执行。Agent 已把每一步都写成用户可复制的命令。

---

## 附：快速命令包（用户可复制）

```bash
# 1. 备份（强烈建议）
git bundle create flybrain-$(date +%Y%m%d).bundle --all
robocopy /E /COPYALL . "..\flybrain-fsbackup-$(date +%Y%m%d)"

# 2. 排查历史
git log --all --diff-filter=A --name-only -- 'flybrain-tier2-backup-*' 'flybrain-connectome-core/**' 'archive/*' | head -50

# 3. A1 清理（如选 keep→ignore）
git rm -r --cached .workbuddy-ai/
echo ".workbuddy-ai/" >> .gitignore

# 4. A4 加 ignore
echo "generated_organisms/" >> .gitignore

# 5. 提交
git add .gitignore
git commit -m "chore: ignore AI memory and root generated_organisms for D3 public readiness"

# 6. C1/C2（若决定公开）
# 编辑 docs/arxiv_paper.md 第 5 与第 33 行，去掉 "currently private, re-publicization planned"
git add docs/arxiv_paper.md
git commit -m "docs: align paper claims with public repo state"

# 7. 最终校验
"C:/Python314/python.exe" scripts/prep_public_release.py --dry-run

# 8. 公开（用户手工，不可撤回）
gh repo edit lm203688/flybrain-connectome --visibility public
```

---

**生成时间**：2026-10-15 15:30（v2.85.0）
**关联文档**：
- `scripts/prep_public_release.py`（扫描脚本，本清单的数据源）
- `docs/RELEASE_GATE_ASSESSMENT_2026-10-14.md`（G3/G5/G7 门槛状态）
- `docs/ARXIV_SUBMIT_META_2026-10-15.md`（P-2/P-3 投稿元数据）
- `docs/PREREGISTRATION_PROTOCOL_v1.md`（R-0.1 R-0.4′ 时间顺序与公开原则）
