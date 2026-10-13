# SPDX-FileCopyrightText: 2026 flybrain-connectome authors
# SPDX-License-Identifier: MIT
"""
core.simulation — Layer 3 仿真引擎层

三个引擎（各带确定性哈希，同一输入两次运行结果一致）：
    ESN  : reservoir + Ridge 回归，输出 7 项能力分数
    GA   : 演化搜索 12 个目标结构（6 拓扑 + 6 功能），fitness 由 ESN 打
    CR   : Combination Reactions，从 25 蓝图 + 27 剖面 + 12 规则池做 4 种原子操作

设计原则：确定性 + 证据化 + 不硬编码真值。
"""
from .esn_engine import (
    esn_engine,
    esn_capability_scores,
    esn_fault_isolation,
    ESN_DEFAULT_PARAMS,
)
from .ga_engine import (
    ga_engine,
    GA_TARGETS,
    GA_DEFAULT_PARAMS,
)
from .combination_reactions import (
    combination_reactions,
    COMBINATION_REACTION_OPS,
)

__all__ = [
    "esn_engine", "esn_capability_scores", "esn_fault_isolation",
    "ESN_DEFAULT_PARAMS",
    "ga_engine", "GA_TARGETS", "GA_DEFAULT_PARAMS",
    "combination_reactions", "COMBINATION_REACTION_OPS",
]
