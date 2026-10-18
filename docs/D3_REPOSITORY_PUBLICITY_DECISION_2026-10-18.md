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

---

## 11. 执行 runbook（可复制命令清单）

> **性质**：所有命令**仅在用户本地机器上执行**。Agent 无 GitHub 账号、无用户 shell 权限、无 arXiv 账号，不代执行任何一步。
> **约定**：每条命令前标注运行终端。PowerShell（`PS>`）与 Git Bash（`$`）不可混用；PowerShell 5.1 不支持 `&&`，多命令用 `;` 分隔。
> **约定**：`$REPO_ROOT = C:\Users\xing\Desktop\flybrain-connectome`（按实际调整）。

### 11.0 前置依赖与账号核查

**终端：PowerShell**

```powershell
# (1) gh CLI 已装
gh --version | Select-Object -First 1

# (2) gh 已认证 + 有 repo scope
$authStatus = gh auth status --json status,scopes -q '.status, .scopes'
Write-Host "status: $authStatus"
if ($authStatus -notcontains 'repo') {
    Write-Host "缺 repo scope，退出"; exit 1
}

# (3) git 版本
git --version

# (4) 安装 git-filter-repo（幂等）
pip install --user git-filter-repo
git-filter-repo --version
```

**判定**：三条命令均返回正常才进入 11.1。

### 11.1 前置备份（Step 1，可回滚）

**终端：PowerShell**

```powershell
$REPO_ROOT = "C:\Users\xing\Desktop\flybrain-connectome"
$STAMP     = Get-Date -Format "yyyyMMdd-HHmmss"
$BUNDLE    = "$REPO_ROOT\flybrain-bundle-$STAMP.bundle"
$BACKUP    = "C:\Users\xing\Desktop\flybrain-fsbackup-$STAMP"

# (1) Git bundle（完整历史 + refs）
git -C $REPO_ROOT bundle create $BUNDLE --all
if ($LASTEXITCODE -ne 0) { Write-Host "BUNDLE 失败，退出"; exit 1 }

# (2) 文件系统快照（含 Tier-2 数据 + 未追踪文件）
robocopy $REPO_ROOT $BACKUP /E /COPYALL /NFL /NDL /NJH /NJS /MT:16
# robocopy exit code 0–7 = 成功，>=8 = 失败
if ($LASTEXITCODE -ge 8) { Write-Host "BACKUP 失败，退出"; exit 1 }

Write-Host "=== 备份成功 ==="
Write-Host "bundle: $BUNDLE"
Write-Host "backup: $BACKUP"
Write-Host "stamp : $STAMP"
```

**验证**：

```powershell
# bundle 应含至少 master + 所有 tag
$heads = git -C $REPO_ROOT bundle list-heads $BUNDLE
if (($heads | Measure-Object).Count -lt 1) { Write-Host "BUNDLE 空，退出"; exit 1 }
Write-Host $heads | Select-Object -First 5

# 快照关键目录存在
Test-Path "$BACKUP\.git"
Test-Path "$BACKUP\male_cns"
Test-Path "$BACKUP\scripts"
```

**回滚点 1**：如后续任一步骤崩溃，可 `git clone $BUNDLE restored-repo` 恢复；快照目录直接作为文件系统恢复源。

### 11.2 前置排查（Step 2，可回滚）

**终端：Git Bash**（跨平台；如用 PowerShell 需将 `$()` 换成 `$env:X`）

```bash
cd "$REPO_ROOT"
mkdir -p .d3_precheck

# (1) .workbuddy-ai/ 历史（v2.67.0 起的残留）
git log --all --diff-filter=A --name-only -- '.workbuddy-ai/*' | sort -u > .d3_precheck/1_workbuddy_ai.txt
wc -l .d3_precheck/1_workbuddy_ai.txt

# (2) Tier-2 备份目录历史
git log --all --diff-filter=A --name-only -- 'flybrain-tier2-backup-*' 'flybrain-connectome-core/*' | sort -u > .d3_precheck/2_tier2.txt
wc -l .d3_precheck/2_tier2.txt

# (3) archive/ 历史（早期可能含敏感内容）
git log --all --diff-filter=A --name-only -- 'archive/*' | sort -u > .d3_precheck/3_archive.txt
wc -l .d3_precheck/3_archive.txt

# (4) Secrets 扫描（若 secret-tool 可用）
"gh secret-tool scan" > .d3_precheck/4_secrets.txt 2>&1 || echo "secret-tool not installed" > .d3_precheck/4_secrets.txt

ls -la .d3_precheck/
```

### 11.3 决策分叉判定（Step 3，可回滚）

**读 11.2 的 4 个文件**：

| 判定条件 | 走路径 | 清洗范围 |
|---|---|---|
| `2_tier2.txt` 非空 | **D-iii 全量清洗** | `.workbuddy-ai/` + `flybrain-tier2-backup-*` + `flybrain-connectome-core/` |
| `1_workbuddy_ai.txt` 非空、`2_tier2.txt` 为空 | **D-ii 局部清洗**（默认） | `.workbuddy-ai/` |
| 两者均空 | **D-i 直接公开** | 无 |

`4_secrets.txt` 有检出：**中止流程**，先 revoke token、修 secret-tool 检出、重跑 11.1–11.2。

### 11.4 D-ii 局部历史清洗（Step 4，可回滚——若 11.5 未跑）

**终端：Git Bash**

```bash
cd "$REPO_ROOT"

# 记录当前 HEAD SHA 供回滚
CURRENT_HEAD=$(git rev-parse HEAD)
echo "$CURRENT_HEAD" > .d3_precheck/current_head.txt

# 单路径清洗（D-ii）
git filter-repo --path .workbuddy-ai --invert-paths --force

# D-iii 追加清洗（仅 11.3 判定为 D-iii 时执行）
# git filter-repo --path 'flybrain-tier2-backup-*' --invert-paths --force
# git filter-repo --path 'flybrain-connectome-core/' --invert-paths --force

# 验证：历史里不应再有这些路径
LEAKS=$(git log --all --oneline --name-only | grep -E 'workbuddy-ai|flybrain-tier2-backup|flybrain-connectome-core' || true)
if [ -n "$LEAKS" ]; then
    echo "STILL PRESENT:"
    echo "$LEAKS"
    exit 1
fi
echo "CLEAN"
```

**回滚点 2**：若 11.5 尚未执行，本地历史可恢复：

```bash
git clone "$BUNDLE" /tmp/flybrain-restore
cd /tmp/flybrain-restore && git reset --hard "$CURRENT_HEAD"
# 或用文件系统快照恢复
```

### 11.5 .gitignore 追加 + commit（Step 5，可回滚）

**终端：PowerShell**

```powershell
$ignoreAdd = @'
# D3 public readiness — 2026-10-18
.workbuddy-ai/
.generated_organisms/
flybrain-tier2-backup-*/
flybrain-connectome-core/
'@
Add-Content -Path ".gitignore" -Value $ignoreAdd -Encoding UTF8

git add .gitignore
git status
git commit -m @'
chore(d3): ignore AI memory and Tier-2 backup paths for public readiness

Blocks re-creation of AI memory and Tier-2 backup paths in future commits.
Preparatory step for the D3 repository publicization decision.

Refs: docs/D3_REPOSITORY_PUBLICITY_DECISION_2026-10-18.md §11.5
'@
```

### 11.6 Force-push 到远端（Step 6，**回滚窗口终点**）

**终端：PowerShell**

```powershell
git push --force origin master
if ($LASTEXITCODE -ne 0) {
    Write-Host "FORCE-PUSH 失败，尚未破坏远端历史，可安全回滚"
    exit 1
}

git push --force origin --tags
if ($LASTEXITCODE -ne 0) {
    Write-Host "TAGS PUSH 失败（master 已推，需重推 tag 或 abort 全部）"
    exit 1
}

Write-Host "FORCE-PUSH 完成"
```

**回滚点 3（关键）**：这是**回滚窗口的最后一步**。若之后任何步骤崩溃，可通过 11.1 的 bundle 从 GitHub 恢复（见 §11.10）。**执行到这里之前，务必确认 11.1–11.5 全部完成**。

### 11.7 公开仓库（Step 7，**不可逆**）

**终端：PowerShell**

```powershell
# 前置确认：gh 认证正常 + repo scope
gh auth status

# 公开仓库（不可撤回——一旦 open 就不能变回 private）
gh repo edit lm203688/flybrain-connectome --visibility public
if ($LASTEXITCODE -ne 0) {
    Write-Host "PUBLICIZE 失败"
    exit 1
}

# 验证
gh repo view lm203688/flybrain-connectome --json visibility -q '.visibility'
# 期望输出：public
```

**注意**：这是**唯一不可逆操作**。之后即使有泄露也无法通过 `--visibility private` 撤回，只能通过 11.10 的 GitHub 界面手动改回 private（数据仍在，只是可见性）。

### 11.8 公开后验证（Step 8）

**终端：PowerShell**

```powershell
# GitHub 页面可访问
$resp = Invoke-WebRequest -Uri "https://github.com/lm203688/flybrain-connectome" -Method Head -UseBasicParsing -TimeoutSec 15
$resp.StatusCode  # 期望 200

# raw.githubusercontent 可访问
$raw = Invoke-WebRequest -Uri "https://raw.githubusercontent.com/lm203688/flybrain-connectome/master/pyproject.toml" -TimeoutSec 15
$raw.Content | Select-String "version" | Select-Object -First 3
```

### 11.9 arXiv 投稿包 + C 类口径对齐（Step 9）

**Agent 已预置在本地工作区，未提交**。用户需检查并 commit。

**终端：Git Bash**

```bash
cd "$REPO_ROOT"

# 检查 ARXIV 提交包已更新（Agent 已改，未提交）
git diff --stat docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md
grep -c "v2.98.1" docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md  # 期望 ≥5
grep -c "47.1%" docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md   # 期望 ≥1（投稿时基线）
grep -c "100.0%" docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md  # 期望 ≥1（v2.98.1 硬门）

# 可选：把 project_version_baseline 从 v2.98.1 改回 v2.98.0（若严格按"投稿时状态"）
# sed -i 's/"project_version_baseline": "v2.98.1"/"project_version_baseline": "v2.98.0"/' \
#     docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md
```

**C 类口径对齐**：改 `docs/arxiv_paper.md` 的 2 处 "currently private" 声明为 "public"：

```bash
# 找出 2 处
grep -n "currently private\|re-publicization" docs/arxiv_paper.md

# 逐处编辑（用户用编辑器打开，或用 sed 单行改）
# 修改 1:
#   原：...MIT License (Tier-1 code; repository currently private, re-publicization planned)
#   新：...MIT License (Tier-1 code; public)
# 修改 2:
#   原：We present a method and a toolkit (currently private, re-publicization planned) that ...
#   新：We present a method and a toolkit that ...
```

**提交**：

```bash
git add docs/arxiv_paper.md docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md
git commit -m @'
docs(d3): align paper claims with public repo state

- Update ARXIV submission package: code_version v2.98.0 -> v2.98.1
- Dual-number S3 discipline effectiveness (47.1% at submission baseline, 100.0% at v2.98.1 post-submission hardening)
- Remove "currently private" claims from arxiv_paper.md (2 locations)

Refs: docs/D3_REPOSITORY_PUBLICITY_DECISION_2026-10-18.md §11.9
'@
git push origin master
```

### 11.10 公开后 24 小时窗口 + 回滚路径（Step 10）

**门禁验证**（PowerShell）：

```powershell
& "C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe" scripts\run_gates.py --quick
# 期望：56/56 PASS

& "C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe" scripts\run_gates.py --full
# 期望：59/59 PASS
```

**arXiv 提交（用户手工）**：

```
打开 https://arxiv.org/help/submit
按 docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md 的 checklist 顺序提交：
  1) P-3 (Four Disciplines)  - 先投，方法论
  2) P-2 (Preregistered Rejection) - 后投，case study
两者在 submission_meta.json 中互引 code_version = v2.98.1
```

### 11.11 回滚路径总表

| 崩在步骤 | 回滚动作 | 数据安全性 |
|---|---|---|
| 11.1 备份 | 不用回滚 | 100% |
| 11.2 排查 | 不用回滚 | 100% |
| 11.3 判定 | 不用回滚 | 100% |
| 11.4 清洗（未 force-push） | `git clone $BUNDLE restored && git reset --hard $CURRENT_HEAD` | 100%（bundle 兜底） |
| 11.5 .gitignore commit | `git reset --hard HEAD~1` | 100% |
| 11.6 force-push 已跑 | `gh repo edit --visibility private`（**只改可见性，不恢复历史**）+ 从 bundle 推回旧历史 | 95%（旧历史需重建） |
| 11.7 已公开 | `gh repo edit --visibility private` + 通知所有 clone 者删除本地副本 + 联系 GitHub 支持删除缓存 | 90%（缓存/镜像可能已扩散） |
| 11.9 arXiv 已提交 | 联系 arXiv 请求撤回（arxiv.org/help/withdraw），提交 v2 时更新 | 85%（v1 会公开可见） |

### 11.12 逐条 checklist 摘要

```
□ 11.0  gh --version / auth status / filter-repo 就绪
□ 11.1  bundle + fsbackup 生成
□ 11.1  bundle list-heads ≥1 行；关键目录存在
□ 11.2  4 条排查命令跑完，快照进 .d3_precheck/
□ 11.3  按快照内容选定 D-i / D-ii / D-iii
□ 11.4  git-filter-repo 清洗完成，CLEAN 通过
□ 11.5  .gitignore 追加 + commit
□ 11.6  force-push master OK；force-push tags OK
□ 11.7  gh repo edit --visibility public OK
□ 11.7  gh repo view visibility = public
□ 11.8  GitHub 页面 200；raw URL 可访问
□ 11.9  ARXIV 包已改（本地已预备）+ arxiv_paper.md 2 处改完
□ 11.9  C 类口径对齐 commit + push
□ 11.10 run_gates --quick 56/56 PASS
□ 11.10 run_gates --full 59/59 PASS
□ 11.10 arXiv 提交 P-3 → P-2（按 submission_order）
```

**执行顺序强制**：Step 1–7 全部完成前不进入 arXiv 提交；Step 7 是**唯一不可逆**，前置步骤全部有回滚路径。

---

**生成时间**：2026-10-18 17:25（v2.98.1 · runbook 附录）
**关联**：
- 主文档：本文件 §1–§10（决策 + 前置准备）
- 基础清单：`docs/PUBLIC_RELEASE_DECISION_CHECKLIST_2026-10-15.md`
- arXiv 提交包：`docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md`
- S3 修复详情：`docs/S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md`
**Agent 状态**：等待用户 D3 拍板 → 用户提供 11.0 通过后逐步确认执行
