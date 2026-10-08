# 快速局部判断实验（北极星 D2 / D3 / D4）

运行：3 拓扑 × 12 试验 / 步，步预算 k=4，质量阈值 0.80，信道噪声 0.12，泄漏 0.90。耗时 0.1s。

## 定义（D1 · `flybrain-connectome-mcp/fast_decision.py`）

比特 `u` 在第 1 步进入 afferent 模块；每步先按接线传播、再按噪声翻转；
`steps_to_quality` = 让某个读出集合上的线性分类器达到 %.2f 准确率所需的**最少步数**。比较的是**固定质量下的时间**，这是此前所有被撤回的结论
（计算力 0/7、能耗 0/24、涌现撤回）都没测过的轴——它们比的都是固定时间预算下的质量。

## D3 结果

| 指标 | 值 |
|---|---|
| n_records | 3 |
| local_afferent_reaches_threshold | 3 |
| local_afferent_1_step | 3 |
| local_afferent_within_horizon | 3 |
| local_remote_reaches_threshold | 0 |
| global_never_reaches | 0 |
| routing_tax_measured | 0 |
| routing_tax_mean_steps | None |
| routing_tax_min_steps | None |
| routing_tax_max_steps | None |

## D2 结构预测

- afferent 模块局部谱半径 vs 决策步数（Spearman）：**0.5**（n=3）
- afferent→remote 接线距离 vs remote 决策步数（Spearman）：**None**（n=0）

## D4 离线整合（「做梦」代理）

| 指标 | 值 |
|---|---|
| sleep_measured_pairs | 3 |
| sleep_shortened_budget | 0 |
| sleep_lengthened_budget | 1 |
| sleep_no_change | 2 |
| sleep_mean_delta_steps | 0.333 |

## 诚实边界

1. **步 = 积分步，不是毫秒**。本框架没有时钟，也没有频率标定。
2. 读出是**在线**的（只用 1..s 步的状态），无未来回看。
3. 噪声是**信道翻转**，不是生物学噪声模型；LEAK/tanh 是工程折衷不是神经生理。
4. 该集合未达阈值 → `steps_to_quality = null`，显式打印，不静默丢弃。
5. 离线整合是「预积分」，不是记忆巩固；无帮助是**结果**，不是缺陷。
6. 本实验测的是**接线决定的路由代价**，不是认知主张。
