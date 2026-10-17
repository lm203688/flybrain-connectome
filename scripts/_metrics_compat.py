"""_metrics_compat.py — AUC/Pearson 兼容层（K5 承重结构）。

将所有 AUC/Pearson 实现收敛到 metrics_kernel。
签名统一为 auc(scores, labels) —— 分数在前，标签在后。

用法：
    from _metrics_compat import auc, pearson  # 替代本地实现

如果 metrics_kernel 不可用（例如未安装 flybrain-core），
回退到纯 Python 实现（与 metrics_kernel 数值一致）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CORE = _ROOT / "flybrain-connectome-core" / "flybrain_core" / "metrics_kernel"

# 尝试从 metrics_kernel 导入
_kernel_available = False
_kernel_auc = None
_kernel_auc_from_pairs = None
_kernel_pearson = None

try:
    _CORE_PARENT = _ROOT / "flybrain-connectome-core"
    if _CORE_PARENT.exists():
        sys.path.insert(0, str(_CORE_PARENT))
    from flybrain_core.metrics_kernel.auc import auc as _kernel_auc, auc_from_pairs as _kernel_auc_from_pairs
    _kernel_available = True
except ImportError:
    pass

try:
    from flybrain_core.metrics_kernel.correlation import pearson_corr as _kernel_pearson
except ImportError:
    _kernel_pearson = None


def _fallback_auc(scores: list[float], labels: list[int]) -> float:
    """纯 Python 回退实现（平均秩法，与 metrics_kernel 一致）。"""
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


def _fallback_auc_from_pairs(pairs: list[tuple[float, int]]) -> float:
    """纯 Python 回退实现。"""
    if not pairs:
        return 0.5
    scores = [p for p, _ in pairs]
    labels = [l for _, l in pairs]
    return _fallback_auc(scores, labels)


def auc(scores: list[float], labels: list[int]) -> float:
    """分类 AUC（Mann-Whitney U，平均秩法）。

    优先使用 metrics_kernel.auc，回退到纯 Python 实现。
    """
    if _kernel_available and _kernel_auc:
        return _kernel_auc(scores, labels)
    return _fallback_auc(scores, labels)


def auc_from_pairs(pairs: list[tuple[float, int]]) -> float:
    """从 (score, label) 对列表计算 AUC。

    优先使用 metrics_kernel.auc_from_pairs，回退到纯 Python 实现。
    """
    if _kernel_available and _kernel_auc_from_pairs:
        return _kernel_auc_from_pairs(pairs)
    return _fallback_auc_from_pairs(pairs)


# 标签在前版本（兼容旧签名 auc_score(y_true, y_score)）
def auc_score(y_true: list[int], y_score: list[float]) -> float:
    """标签在前版本的 AUC（兼容 mechanism_binary.py 旧签名）。"""
    return auc(y_score, y_true)


def _fallback_pearson(a: list[float], b: list[float]) -> float:
    """纯 Python 回退实现（样本 Pearson 相关系数）。"""
    n = len(a)
    if n < 2 or len(b) != n:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da <= 1e-15 or db <= 1e-15:
        return 0.0
    return num / (da * db)


def pearson(a: list[float], b: list[float]) -> float:
    """Pearson 相关系数。

    优先使用 metrics_kernel.correlation.pearson_corr，回退到纯 Python 实现。
    """
    if _kernel_pearson:
        return _kernel_pearson(a, b)
    return _fallback_pearson(a, b)
