"""_kernel_bridge.py — metrics_kernel 兼容层（selfverify 内部）。

将 selfverify.gate 的 AUC/Pearson 实现委托到 metrics_kernel，
确保所有度量来自单一真源（K5 承重结构）。

如果 metrics_kernel 不可用，回退到纯 Python 实现。
"""
from __future__ import annotations

import sys
from pathlib import Path

_KERNEL_AVAILABLE = False
_kernel_auc = None
_kernel_pearson = None

# 尝试从 metrics_kernel 导入
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CORE_PARENT = _ROOT / "flybrain-connectome-core"
if _CORE_PARENT.exists():
    try:
        sys.path.insert(0, str(_CORE_PARENT))
        from flybrain_core.metrics_kernel.auc import auc as _kernel_auc
        _KERNEL_AVAILABLE = True
    except ImportError:
        pass

try:
    from flybrain_core.metrics_kernel.correlation import pearson as _kernel_pearson
    if _kernel_pearson:
        pass  # already available
except ImportError:
    _kernel_pearson = None


def _fallback_auc(scores: list[float], labels: list[int]) -> float:
    """纯 Python 回退实现（平均秩法）。"""
    n = len(scores)
    if n == 0 or len(labels) != n:
        return 0.5
    label_set = set(labels)
    if not label_set.issubset({0, 1}):
        raise ValueError(f"labels must be binary (0 or 1), got {label_set}")
    n_pos = sum(1 for l in labels if l == 1)
    n_neg = sum(1 for l in labels if l == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    paired = sorted(zip(scores, labels))
    rank_of = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and paired[j + 1][0] == paired[i][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            rank_of[k] = avg_rank
        i = j + 1
    r_pos = sum(rank_of[k] for k, (_, l) in enumerate(paired) if l == 1)
    u = r_pos - n_pos * (n_pos + 1) / 2.0
    auc_val = u / (n_pos * n_neg)
    return max(0.0, min(1.0, auc_val))


def _fallback_pearson(a: list[float], b: list[float]) -> float:
    """纯 Python 回退实现。"""
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def auc(scores: list[float], labels: list[int]) -> float:
    """分类 AUC。优先使用 metrics_kernel，回退到纯 Python。"""
    if _KERNEL_AVAILABLE and _kernel_auc:
        return _kernel_auc(scores, labels)
    return _fallback_auc(scores, labels)


def pearson(a: list[float], b: list[float]) -> float:
    """Pearson 相关系数。优先使用 metrics_kernel，回退到纯 Python。"""
    if _kernel_pearson:
        return _kernel_pearson(a, b)
    return _fallback_pearson(a, b)
