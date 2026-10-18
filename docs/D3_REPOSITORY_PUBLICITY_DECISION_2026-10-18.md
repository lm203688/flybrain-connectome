# D3 仓库公开决策材料 — v2.98.1 · 2026-10-18

**前置**：本文件是"决策准备包"，不是执行日志。Agent 已把所有不可逆动作（重写历史、公开仓库、修改论文口径）拆成用户可复制的命令，Agent 不代决策。
**版本基线**：v2.98.1（本轮补丁发布：W1–W7 全部关闭，S3 catch-rate 47.1% → 100%，门禁 56/56 quick + 59/59 full PASS）
**用户指令背景**：2026-10-18 用户明确"投递 P-2/P-3 到 arXiv。D3 仓库公开决策。W1–W7 七项 gate 漏洞要修。所有任务做好以后再修改论文材料"。
**关联文档**：
- `docs/PUBLIC_RELEASE_DECISION_CHECKLIST_2026-10-15.md`（v2.85.0 决策清单，本文件的**基础**）
- `docs/SCI_READINESS_ASSESSMENT_2026-10-18.md`（8 项公开门槛状态）
- `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md`（P-2/P-3 投稿包）
- `docs/S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md`（W1–W7 修复详情）

---

## 0. 一句话结论

**推荐：D3 立即公开（走 D-ii 局部历史清洗 → 直接 open）**，因为 v2.98.1 后 W1–W7 全部关闭，S3 catch-rate 达到 100%，P-2/P-3 短文已无阻塞项。P-1 主线延后（D1 机制 + Xu 2026 需要更多时间消化）。

**但**：D3 公开是不可逆操作（一旦 open 就不能撤回私有），必须先做历史清洗备份。Agent 无法代做，需用户手工执行。

---

## 1. 决策矩阵（4 选项）

| 选项 | 说明 | 风险 | 成本 | 对 arXiv 影响 |
|---|---|---|---|---|
| **D-i** 直接公开 | 假设历史干净，`gh repo edit --visibility public` | 若历史含 Tier-2 数据 = **不可逆泄露** | 0 | P-2/P-3 立即投，P-1 需补机制证据 |
| **D-ii** 局部历史清洗 + 公开 | `git filter-repo` 删 `.workbuddy-ai/` + 抽查 Tier-2 → force-push → open | 中等（需备份 + rebase） | 1–2 小时 | 同上，但更安全 |
| **D-iii** 全量历史重建 | `git filter-repo` 从头重建，只保留 Tier-1 代码 | 高（所有分支 force-push） | 半天 + 备份 | 最安全但成本高 |
| **D-iv** 延迟公开 | 不重写，继续私有；等 arXiv 收到回复后再定 | 与"SCI 硬门槛"目标冲突 | 0 | P-2/P-3 阻塞（无 code URL），只能投方法学短文；P-1 延后 |

**推荐：D-ii**。理由：
- 历史里有 `.workbuddy-ai/` 追踪残留（v2.67.0 起）+ 可能的早期 archive 快照
- Tier-2 数据目录虽当前 `.gitignore`，但**历史提交里可能包含早期内容**
- 局部清洗成本可控（1–2 小时），安全边际高
- 不阻塞 arXiv 投稿窗口

---

## 2. 前置备份（无论选哪个 D 选项）

Tier-2 数据不可再生，动手前**必须**备份：

```bash
# 备份 1：Git bundle（推荐，最小体积，完整历史）
git bundle create flybrain-$(date +%Y%m%d-%H%M%S).bundle --all

# 备份 2：文件系统快照（Tier-2 数据 + 未追踪文件）
robocopy /E /COPYALL "C:\Users\xing\Desktop\flybrain-connectome" \
    "C:\Users \xing\Desktop\flybrain-fsbackup-$(date +%Y%m%d)"

# 验证备份
git bundle list-heads flybrain-*.bundle | head -5
ls -la flybrain-fsbackup-*/  | head -5
```

---

## 3. 历史排查（4 条命令，用户手工执行）

```bash
# 1. Tier-2 数据是否曾出现在历史提交？
git log --all --diff-filter=A --name-only \
    -- 'flybrain-tier2-backup-*' 'flybrain-connectome-core/**' | head -30

# 2. archive/ 早期内容
git log --all --diff-filter=A --name-only -- 'archive/*' | head -30

# 3. AI memory 目录历史
git log --all --oneline -- '.workbuddy-ai/*' '.workbuddy/*' | head -20

# 4. Secrets 扫描（若装了 gh secret-tool）
"gh secret-tool scan" 2>/dev/null || echo "secret-tool not installed"
```

**判定**：
- 若 #1/#2 有输出 → 必须走 D-ii 或 D-iii
- 若 #3 有输出（v2.67.0 起的 `.workbuddy-ai/` 追踪）→ 必须走 D-ii
- 若 #4 检出 secret → 必须先 revoke 再重写历史

---

## 4. D-ii 局部历史清洗（推荐路径）

```bash
# 安装 filter-repo（若未装）
pip install git-filter-repo

# 只删 AI memory 目录（最小干预）
git filter-repo --path .workbuddy-ai --invert-paths

# 若 #1 排查有输出，追加 Tier-2 路径
git filter-repo --path 'flybrain-tier2-backup-*' --invert-paths
git filter-repo --path 'flybrain-connectome-core/' --invert-paths

# 验证：历史里不应再有这些路径
git log --all --oneline --name-only | grep -E "tier2|workbuddy-ai|flybrain-connectome-core" && echo "STILL PRESENT" || echo "CLEAN"

# force-push（本地 → 远端）
git push --force origin master
git push --force origin --tags
```

**验证后清理 `.gitignore`**：
```bash
# 确保未来不再追踪
echo ".workbuddy-ai/" >> .gitignore
echo "generated_organisms/" >> .gitignore
echo "flybrain-tier2-backup-*/" >> .gitignore
echo "flybrain-connectome-core/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore AI memory and Tier-2 backup paths for D3 public readiness"
```

---

## 5. C 类口径对齐（公开后执行）

公开后修改 `docs/arxiv_paper.md` 的 2 处"currently private"声明：

```diff
- lm203688/flybrain-connectome` · MIT License (Tier-1 code; repository currently private, re-publicization planned)
+ lm203688/flybrain-connectome` · MIT License (Tier-1 code; public)

- We present a method and a toolkit (currently private, re-publicization planned) that converts ...
+ We present a method and a toolkit that converts ...
```

```bash
git add docs/arxiv_paper.md
git commit -m "docs: align paper claims with public repo state (D3 publicized)"
```

---

## 6. 最终公开（不可逆）

```bash
# 检查 GitHub token 有 repo scope
gh auth status

# 公开仓库（不可撤回）
gh repo edit lm203688/flybrain-connectome --visibility public

# 验证
gh repo view lm203688/flybrain-connectome --json visibility
```

**验证公开后**：
```bash
# 检查公开 URL 可访问
curl -sI https://github.com/lm203688/flybrain-connectome | head -3
# 检查 code URL 在 arXiv 投稿包里有效
curl -s https://raw.githubusercontent.com/lm203688/flybrain-connectome/master/pyproject.toml | grep version
```

---

## 7. 公开后 24 小时窗口（arXiv 提交准备）

公开后立即执行：

1. **验证 code URL 可访问**：`curl -sI https://github.com/lm203688/flybrain-connectome`
2. **更新 arXiv 投稿包**：
   - `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` 中的 `code_version` 从 v2.98.0 → v2.98.1
   - `submission_meta.json` 中 `project_version_baseline` 同步更新
   - 可选：把 v2.98.1 的 100% catch-rate 作为"投稿后修复"注记加到 comments
3. **提交 P-2/P-3**（用户手工，Agent 无 arXiv 账号）：
   - 打开 https://arxiv.org/help/submit
   - 按 `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` 的 checklist 提交
4. **P-1 主线延后**：等 D1 机制证据（Xu 2026 的 E4 B-14 区室边界落地）再投

---

## 8. Agent 已就绪 / 用户待决策

| 项 | 状态 |
|---|---|
| 决策准备包（本文件） | ✅ 落地 |
| 排查命令（4 条） | ✅ 已写，用户手工执行 |
| D-ii 局部清洗命令 | ✅ 已写，用户手工执行 |
| C1/C2 口径对齐 | ⏳ 依赖 D3 公开 |
| 备份命令 | ⏳ 用户执行（Tier-2 不可再生） |
| 公开操作 `gh repo edit` | ⏳ 用户执行（不可撤回） |
| arXiv 提交 | ⏳ 用户执行（无 Agent arXiv 账号） |

**Agent 边界**：所有不可逆操作（历史重写、公开仓库、arXiv 提交、论文口径修改）均不代做——这些必须由用户显式确认后手动执行。Agent 已把每一步都写成可复制的命令。

---

## 9. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 历史里含 Tier-2 数据 | 中 | **不可逆泄露** | 必须做 D-ii 排查 |
| force-push 覆盖本地工作 | 低 | 数据丢失 | 前置备份 |
| arXiv 审核慢于预期 | 高 | P-2/P-3 延迟 | 提前准备，公开后立即投 |
| GitHub 封禁/限流 | 低 | 无法公开 | 提前验证 `gh auth status` |
| Xu 2026 论文细节争议 | 低 | P-1 延后 | P-1 本就延后，不影响 P-2/P-3 |

---

## 10. 下一步（用户拍板后）

1. **用户执行**：备份 → 排查 → D-ii 清洗 → C1/C2 对齐 → 公开
2. **Agent 执行**：公开后立即更新 arXiv 投稿包（code_version → v2.98.1）
3. **用户执行**：arXiv 提交 P-2/P-3
4. **Agent 执行**：更新 `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` 记录实际提交状态
5. **最后**：按用户指令"所有任务做好以后再修改论文材料"——更新 P-2/P-3 的 catch-rate 数字（47.1% → 100%）

---

**生成时间**：2026-10-18 16:35（v2.98.1）
**关联**：`docs/PUBLIC_RELEASE_DECISION_CHECKLIST_2026-10-15.md`（v2.85.0 基础清单）
**Agent 状态**：等待用户 D3 拍板
