"""selfverify.dynamics — S3 最小动力学读出。

实现最小可行动力学度量，用于检测系统的时间行为特征：
- 恢复时间常数（tau_recovery）
- 振荡频率（frequency）
- 稳态偏差（steady_state_bias）
- 衰减率（decay_rate）

这些度量是独立于具体实验的通用动力学特征，可应用于任何时间序列数据。

参考：
  - F2 恢复动力学：三补偿机制（R-a/R-b/R-c）
  - 时间序列分析基础：自相关、频谱分析
"""
from __future__ import annotations

import math
from typing import Any, Optional


# 时间常数（离散步）
TAU_A = 2.0   # 快速机制：路径募集
TAU_B = 5.0   # 中速机制：权重重分配
TAU_C = 8.0   # 慢速机制：稳态增益


def recovery_trajectory(
    modulators: dict[str, float],
    drop_magnitude: float,
    T: int,
    enabled: Optional[set[str]] = None,
) -> list[float]:
    """计算恢复轨迹 r(t)，t = 0..T。
    
    r_total(t) = min(1.0, sum_m r_m(t)) * drop_magnitude
    
    每个机制的贡献：r_m(t) = ceiling_m * modulator_m * (1 - exp(-t/tau_m))
    
    Args:
        modulators: 各机制的调节器值 {R_a: float, R_b: float, R_c: float}
        drop_magnitude: 故障幅度
        T: 时间步长
        enabled: 启用的机制集合（默认全部启用）
    
    Returns:
        恢复轨迹曲线 [r(0), r(1), ..., r(T)]
    """
    if enabled is None:
        enabled = {"R_a", "R_b", "R_c"}
    
    taus = {"R_a": TAU_A, "R_b": TAU_B, "R_c": TAU_C}
    
    curve = [0.0]
    for t in range(1, T + 1):
        total = 0.0
        for mech in enabled:
            mod = modulators.get(mech, 0.0)
            if mod > 0.0:
                tau = taus.get(mech, 1.0)
                total += mod * (1.0 - math.exp(-t / tau))
        curve.append(min(1.0, total) * drop_magnitude)
    
    return curve


def recovery_auc(curve: list[float], drop_magnitude: float) -> float:
    """计算归一化恢复 AUC（面积）。
    
    recovery_AUC = (1/T) * sum_t r(t) / drop_magnitude
    
    表示故障被补偿的比例，范围 [0, 1]。
    
    Args:
        curve: 恢复轨迹曲线
        drop_magnitude: 故障幅度
    
    Returns:
        归一化恢复 AUC
    """
    T = len(curve) - 1
    if T <= 0 or drop_magnitude <= 0:
        return 0.0
    total = sum(curve[1:]) / T
    return max(0.0, min(1.0, total / drop_magnitude))


def t_half(curve: list[float], drop_magnitude: float) -> Optional[float]:
    """计算半恢复时间。
    
    第一个 t 使得 r(t)/drop_magnitude >= 0.5
    
    Args:
        curve: 恢复轨迹曲线
        drop_magnitude: 故障幅度
    
    Returns:
        半恢复时间（步数），如果未达到 50% 则返回 None
    """
    if drop_magnitude <= 0:
        return 0.0
    T = len(curve) - 1
    if T <= 0:
        return None
    for i in range(1, T + 1):
        if curve[i] / drop_magnitude >= 0.5:
            return float(i)
    return None


def tau_recovery(curve: list[float], drop_magnitude: float) -> Optional[float]:
    """估计恢复时间常数。
    
    通过拟合指数衰减模型 r(t) = 1 - exp(-t/tau) * drop_magnitude
    
    使用半恢复时间作为 tau 的近似：tau ≈ t_half / ln(2)
    
    Args:
        curve: 恢复轨迹曲线
        drop_magnitude: 故障幅度
    
    Returns:
        恢复时间常数估计，如果无法计算则返回 None
    """
    t_h = t_half(curve, drop_magnitude)
    if t_h is not None and t_h > 0:
        return t_h / math.log(2)
    return None


def oscillation_frequency(curve: list[float], baseline: Optional[float] = None) -> Optional[float]:
    """检测振荡频率。
    
    通过零交叉率估计：frequency = n_zero_crossings / (T * 2)
    
    Args:
        curve: 时间序列曲线
        baseline: 基准值（默认使用均值）
    
    Returns:
        振荡频率（周期数/步），如果无法检测则返回 None
    """
    if len(curve) < 3:
        return None
    
    if baseline is None:
        baseline = sum(curve) / len(curve)
    
    # 计算零交叉
    n_crossings = 0
    for i in range(1, len(curve)):
        prev_diff = curve[i-1] - baseline
        curr_diff = curve[i] - baseline
        if (prev_diff <= 0 and curr_diff > 0) or (prev_diff > 0 and curr_diff <= 0):
            n_crossings += 1
    
    T = len(curve) - 1
    if T <= 0:
        return None
    
    # 频率 = 零交叉数 / (2 * T)（每个完整周期有两次零交叉）
    return n_crossings / (2 * T)


def decay_rate(curve: list[float]) -> Optional[float]:
    """计算衰减率。
    
    通过线性回归估计：log(r(t)) = -t * decay_rate + const
    
    使用简单实现：比较前后段均值
    
    Args:
        curve: 时间序列曲线
    
    Returns:
        衰减率（正值表示衰减，负值表示增长），如果无法计算则返回 None
    """
    if len(curve) < 4:
        return None
    
    T = len(curve) - 1
    # 比较前半段和后半段
    mid = len(curve) // 2
    first_half = sum(curve[:mid]) / mid
    second_half = sum(curve[mid:]) / (len(curve) - mid)
    
    if first_half <= 0:
        return None
    
    # 衰减率 ≈ ln(first_half / second_half) / (T/2)
    if second_half <= 0:
        return float('inf')
    
    return math.log(first_half / second_half) / (T / 2)


def steady_state_bias(curve: list[float], target: float = 1.0) -> float:
    """计算稳态偏差。
    
    最后 20% 的时间点的平均值与目标的偏差
    
    Args:
        curve: 时间序列曲线
        target: 目标值（默认 1.0）
    
    Returns:
        稳态偏差（正值表示未达标，负值表示超额）
    """
    if len(curve) < 5:
        return target - curve[-1] if curve else 0.0
    
    # 最后 20% 的点
    n_tail = max(1, len(curve) // 5)
    tail = curve[-n_tail:]
    steady_value = sum(tail) / n_tail
    
    return target - steady_value


def compute_all(
    modulators: dict[str, float],
    drop_magnitude: float,
    T: int,
    enabled: Optional[set[str]] = None,
) -> dict[str, Any]:
    """计算所有动力学度量。
    
    Args:
        modulators: 各机制的调节器值
        drop_magnitude: 故障幅度
        T: 时间步长
        enabled: 启用的机制集合
    
    Returns:
        包含所有动力学位度的字典
    """
    curve = recovery_trajectory(modulators, drop_magnitude, T, enabled)
    
    return {
        "curve": curve,
        "recovery_auc": recovery_auc(curve, drop_magnitude),
        "t_half": t_half(curve, drop_magnitude),
        "tau_recovery": tau_recovery(curve, drop_magnitude),
        "oscillation_frequency": oscillation_frequency(curve),
        "decay_rate": decay_rate(curve),
        "steady_state_bias": steady_state_bias(curve),
        "modulators": modulators,
        "drop_magnitude": drop_magnitude,
        "T": T,
        "enabled": sorted(enabled) if enabled else ["R_a", "R_b", "R_c"],
    }


def variance_over_trajectories(
    trajectories: list[dict[str, Any]],
    key: str = "recovery_auc",
) -> float:
    """计算多个轨迹的某个度量的方差。
    
    用于检测度量是否有真实方差（非退化）。
    
    Args:
        trajectories: 多个动力学计算结果
        key: 要计算方差的度量键
    
    Returns:
        方差值
    """
    values = [t.get(key) for t in trajectories if t.get(key) is not None]
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance


def zero_ratio(curve: list[float]) -> float:
    """计算曲线中零值的比例。
    
    用于检测退化（所有值为 0）。
    
    Args:
        curve: 时间序列曲线
    
    Returns:
        零值比例
    """
    if not curve:
        return 0.0
    n_zero = sum(1 for v in curve if v == 0.0)
    return n_zero / len(curve)
