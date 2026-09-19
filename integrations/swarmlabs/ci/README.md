# Phase 4 CI 集成指南

## 三种集成方式

### 方式 1：本地手动验证（推荐，零依赖）

最简方案：在 SwarmLabs 侧配一个本地脚本，PR 前手动跑。

**SwarmLabs 侧需要做的**：
```bash
# 1. 安装依赖
pip install scipy

# 2. 配置 flybrain-connectome 路径
export FLYBRAIN_PATH="/path/to/flybrain-connectome"

# 3. 运行验证
python "$FLYBRAIN_PATH/integrations/swarmlabs/run_phase4_checks.py" --quick
```

**预期结果**：4/4 项全绿（sync + cross_domain + batch + profile）

### 方式 2：GitHub Actions 手动触发（中等成本）

**SwarmLabs 侧需要做的**：
1. 把 `ci/flybrain-phase4.yml` 复制到 `.github/workflows/flybrain-phase4.yml`
2. 在 SwarmLabs 仓库配置 secret：`FLYBRAIN_PATH`（指向 flybrain-connectome 的路径）
3. 手动触发：
   ```bash
   gh workflow dispatch --workflow flybrain-phase4.yml \
     -f mode=quick -f blueprint=deep_reasoning
   ```

**权限要求**：需要 Workflows:write PAT 权限（SwarmLabs 当前 PAT 缺此权限）

### 方式 3：GitHub Actions 自动触发（高成本，不推荐）

**SwarmLabs 侧需要做的**：
1. 配置 flybrain-connectome 作为 git submodule（但 flybrain 是闭源，需要 private repo 权限）
2. 取消 `push:` 或 `schedule:` 注释
3. 每次 PR 合入自动跑验证

**权限要求**：需要 `Contents:read` + `Workflows:write` + flybrain private repo 访问权

## 推荐方案

**方式 1（本地手动）+ 方式 2（手动触发）组合**：
- 日常开发用方式 1，零成本
- 发布前用方式 2 跑一次完整验证，记录到 CI artifact
- 不上自动触发（避免闭源项目权限问题）

## 验证脚本清单

| 脚本 | 用途 | 耗时 | 依赖 |
|---|---|---|---|
| `check_swarmlabs_sync.py` | 26 organism 一致性体检 | ~2s | 无 |
| `e2e_cross_domain.py` | 3 任务 × 4 配置跨域对比 | ~53s | scipy |
| `e2e_batch_scenarios.py` | 10 场景 × 2 配置批量验证 | ~47s | scipy |
| `e2e_batch_stats.py` | 5 场景 × 2 配置 × 3 轮统计 | ~60s | scipy |
| `profile_compare.py` | cProfile CPU 剖析 | ~7s | scipy |
| `blueprint_selector.py` | 蓝图选择启发式（无需运行 SwarmLabs） | ~2s | 无 |
| `run_phase4_checks.py` | 一键运行（--quick / --ci / --full） | ~2-3min | scipy |

## CI 模式参数

| 模式 | 内容 | 耗时 | 用途 |
|---|---|---|---|
| `--quick` | sync + profile | ~10s | 日常开发 |
| `--ci` | sync + cross_domain + batch + profile | ~2min | 发布前 |
| `--full` | 全部 + 统计显著性 | ~5min | 重大版本 |

## 已知限制

1. **闭源项目**：flybrain-connectome 是闭源项目，CI 需要配置私仓访问
2. **PAT 权限**：SwarmLabs 当前 PAT 缺 `Workflows:write`，无法编辑 workflow YAML
3. **依赖**：Phase 4 新增 `scipy` 依赖（36.6MB），需要 SwarmLabs 侧确认是否接受
4. **耗时**：完整 CI ~2-5 分钟，可能拖慢 PR 反馈循环
