# 🚀 最终 Launch 清单（40 分钟版）

**项目状态**：v3.00.2 · 58/58 gates PASS · GitHub Pages 已上线 · **MCP Registry 已发布** · 8/8 MCP PRs 提交 · PyPI 名称可用

---

## 📦 Launch 三大项（按依赖顺序）

### ✅ 1️⃣ MCP Registry 发布（已完成 2026-10-25）
- **URL**：https://registry.modelcontextprotocol.io/v0.1/servers/io.github.lm203688%2Fflybrain-connectome/versions/3.0.2
- **状态**：active, isLatest=true
- **方式**：`mcp-publisher publish server.json`（使用 GitHub PAT 非交互式登录）
- **文件**：`mcp-registry/server.json` + `scripts/publish_mcp_registry.sh`
- **意义**：官方 MCP 服务器注册表（7.4k⭐），MCP 生态最高含金量入口

### 2️⃣ 提交 Glama.ai（5 分钟，最高优先）
- **URL**：https://glama.ai/mcp/servers/new
- **原因**：punkpeye/awesome-mcp-servers#17478（86k⭐）被 bot 要求必须加 Glama badge
- **表单关键字段**（从 bot 评论 + 现有 servers 反推）：
  - **Repository**：`lm203688/flybrain-connectome`
  - **Subdirectory**（可选）：`flybrain-connectome-mcp`
  - **Dockerfile**：必须添加（bot 明确说 "you must add Dockerfile directly to Glama"）
  - **Description**：`Auditable multi-agent topology generator from Drosophila MaleCNS v1.0 connectome. 36 MCP tools, 62 gates, LangGraph/CrewAI/AutoGen exports.`
  - **Check 要求**：server 必须 start + respond to introspection requests（我们的 `flybrain serve` 就是 MCP server）
- **完成后**：回到 https://github.com/punkpeye/awesome-mcp-servers/pull/17478 加 badge，bot 会自动通过
- **Badge 格式**（bot 给的模板）：
  ```markdown
  [![lm203688/flybrain-connectome MCP server](https://glama.ai/mcp/servers/lm203688/flybrain-connectome/badges/score.svg)](https://glama.ai/mcp/servers/lm203688/flybrain-connectome)
  ```

### 3️⃣ 发布 PyPI（15 分钟）
- **名称可用**：`flybrain-connectome`（pypi.org/pypi/flybrain-connectome/json → HTTP 404 ✅）
- **dist 已就绪**：`dist/`（sdist 574 KB + wheel 577 KB，已通过 twine check）
- **一键脚本**：`bash scripts/publish_pypi.sh`
- **步骤**：
  1. 注册 pypi.org 账号（如果用现有账号跳过）
  2. https://pypi.org/manage/account/token/ → 创建 API token
  3. `export TWINE_USERNAME=__token__`
  4. `export TWINE_PASSWORD=pypi-xxxxxxxxxxxxxxxxxxxxxxxx`（你的 token）
  5. `bash scripts/publish_pypi.sh`
- **验证**：`curl https://pypi.org/pypi/flybrain-connectome/json` 应返回 200
- **PyPI 页面**：`https://pypi.org/project/flybrain-connectome/`（用户会看到作者名 Li Xing / 李星 ✅ 已统一）

### 4️⃣ 提交 bioRxiv（20 分钟）
- **URL**：https://www.biorxiv.org/（或 https://www.biorxiv.org/submit）
- **指南**：`outputs/SCI_SUBMISSION_PACKAGE_2026-10-20/02_submission_guides/BIORXIV_SUBMISSION_PASTE_READY.md`
- **顺序**：先 P-3（PR-2b 预执行拒绝案例）→ 再 P-2（S6-S9 四纪律方法学）
- **5 步预提交清单**（指南里第 2 章）：
  1. 作者列表确认（Li Xing 第一作者，ORCID 0000-0002-8747-1969）
  2. 数据可用性声明（GitHub repo 已 public，MaleCNS 引用已核对）
  3. 利益冲突声明（无）
  4. 伦理声明（不涉及人类受试者/动物，仅公开连接组数据）
  5. 附件确认（数据可用性声明 + 声明文件 + 补充材料）
- **不需要**：arXiv endorsement（bioRxiv 无此要求）、APC（$0）

---

## 📊 MCP 生态 PR 状态（2026-10-25 更新）

| PR | 状态 | 反馈处理 |
|---|---|---|
| **MCP Registry** | ✅ **已发布** | 官方注册表，status=active |
| punkpeye/awesome-mcp-servers#17478 (86k⭐) | 🟡 open | 需 Glama badge（bot 要求）→ 待用户提交 Glama |
| punkpeye/awesome-remote-mcp-servers#2801 (1.8k⭐) | ⚫ **已诚实关闭** | 无 hosted 端点 → 附说明 + 指向 punkpeye/awesome-mcp-servers |
| rohitg00/awesome-devops-mcp-servers#380 (1k⭐) | 🟢 **已修 4 条 CodeRabbit** | 62 gates / 新 Multi-Agent Orchestration 子区 / 去 EU AI Act / PROV-JSON 注 optional |
| yzfly/Awesome-MCP-ZH#834 (7.7k⭐) | 🟡 open | 无反馈，待合并 |
| MobinX/awesome-mcp-list#928 | 🟡 open | 无反馈，待合并 |
| cobanov/awesome-fly#26 | 🟡 open | 无反馈，待合并 |
| cryptotaxi247/awesome-mcp-servers#1 | 🟡 open | 无反馈，待合并 |
| ceesem/awesome-connectomics#1 | 🟡 open | 无反馈，待合并 |

**本轮净进展**：✅ MCP Registry 发布（官方注册表）+ 1 个 PR 关闭（诚实）+ 1 个 PR 修完全部 CodeRabbit 反馈 + 1 个 PR 加 Glama 提交中说明。

---

## 🎯 40 分钟预算分配

| 时间 | 任务 | 依赖 |
|---|---|---|
| ~~0-5 min~~ | ~~MCP Registry 发布~~ | ✅ **已完成** |
| 0-5 min | Glama.ai 提交 | 打开浏览器 + GitHub OAuth |
| 5-20 min | PyPI 发布 | pypi.org 账号 + token |
| 20-40 min | bioRxiv 提交 P-3 | 作者信息已确认 |
| 40+ min | 回到 punkpeye/awesome-mcp-servers#17478 加 Glama badge | Glama 上架完成 |

---

## 📁 关键文件路径（本机上）

- MCP Registry 配置：`C:\Users\xing\Desktop\flybrain-connectome\mcp-registry\server.json`
- MCP Registry 发布脚本：`C:\Users\xing\Desktop\flybrain-connectome\scripts\publish_mcp_registry.sh`
- PyPI 一键脚本：`C:\Users\xing\Desktop\flybrain-connectome\scripts\publish_pypi.sh`
- PyPI 模板：`C:\Users\xing\Desktop\flybrain-connectome\.pypirc`（模板，填 token 后改名 `.pypirc`）
- dist 目录：`C:\Users\xing\Desktop\flybrain-connectome\dist\`
- bioRxiv 指南：`C:\Users\xing\Desktop\flybrain-connectome\outputs\SCI_SUBMISSION_PACKAGE_2026-10-20\02_submission_guides\BIORXIV_SUBMISSION_PASTE_READY.md`
- P-3 稿件：`C:\Users\xing\Desktop\flybrain-connectome\outputs\SCI_SUBMISSION_PACKAGE_2026-10-20\01_manuscripts\PAPER_P3_JOSS_PREREG_DISCIPLINE.md`
- 声明文件：`C:\Users\xing\Desktop\flybrain-connectome\outputs\SCI_SUBMISSION_PACKAGE_2026-10-20\03_declarations\`

---

## 🔑 本轮（2026-10-25 08:40-09:20）完成清单

- ✅ **MCP Registry 发布**：使用 `mcp-publisher` CLI + GitHub PAT 非交互式登录，成功发布到官方 MCP 注册表
- ✅ 创建 `mcp-registry/server.json`（验证通过）
- ✅ 创建 `scripts/publish_mcp_registry.sh`（支持 --validate/--login/--publish）
- ✅ 搜索发现 4 个新 MCP 目录（appcypher 已归档，wong2/YuzeHao2023/TensorBlock 待提交）
- ✅ 更新 MCP_ECOSYSTEM_SUBMISSION_PACKAGE.md（反映 MCP Registry 已发布）
- ✅ 核验 8 个 MCP PR 状态：7 open + 1 closed

---

## 🔑 上一轮（2026-10-24 21:00-21:30）完成清单

- ✅ 核验 8 个 MCP PR 状态：5 个无反馈 / 3 个有 bot 反馈
- ✅ 修复 rohitg00/devops-mcp#380 全部 4 条 CodeRabbit 反馈
- ✅ 诚实关闭 punkpeye/awesome-remote-mcp-servers#2801
- ✅ punkpeye/awesome-mcp-servers#17478 加 Glama 提交中说明
- ✅ 核验 PyPI 名称可用（HTTP 404）
- ✅ 核验 GitHub Pages 已上线（root + demo HTTP 200）

---

*更新：2026-10-25 09:20 · v3.00.2 · 58/58 gates PASS · MCP Registry 已发布*
