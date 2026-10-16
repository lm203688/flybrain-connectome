"""selfverify.metric_versions — M2.5 度量族版本化机制。

设计度量族版本化协议，确保度量定义的版本可追溯、兼容性可检查、
迁移规则可执行。

核心组件：
- MetricFamily: 度量族定义（名称、版本、描述）
- MetricVersion: 单个度量版本的元数据
- CompatibilityMatrix: 版本间兼容性矩阵
- MigrationRule: 版本升级迁移规则
- Registry: 度量族注册表（全局单例）

参考：
  - PR-2b 预执行拒绝：recovery_AUC 与 drop_magnitude 的解析耦合
  - S7 分辨率预检：标签阈值与数据范围的匹配
  - C3 rank 标签：绝对阈值 → 分位标签的迁移
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# 版本标识符格式：MAJOR.MINOR.PATCH
# MAJOR: 不兼容的 API 变更
# MINOR: 向后兼容的功能新增
# PATCH: 向后兼容的问题修复


@dataclass
class Version:
    """语义化版本标识符。"""
    major: int
    minor: int = 0
    patch: int = 0
    
    def __post_init__(self):
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("版本分量必须非负")
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))
    
    def __lt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __le__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)
    
    def __gt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)
    
    def __ge__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)
    
    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """从字符串解析版本。"""
        parts = version_str.split(".")
        if len(parts) == 1:
            return cls(int(parts[0]))
        elif len(parts) == 2:
            return cls(int(parts[0]), int(parts[1]))
        elif len(parts) == 3:
            return cls(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            raise ValueError(f"无效的版本格式: {version_str}")
    
    def to_dict(self) -> dict[str, int]:
        return {"major": self.major, "minor": self.minor, "patch": self.patch}


@dataclass
class MetricDefinition:
    """单个度量的定义。"""
    name: str
    version: Version
    description: str
    formula: str
    range: Optional[str] = None  # 例如 "[0, 1]"
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他度量名称
    tags: list[str] = field(default_factory=list)  # 分类标签
    created_at: str = ""
    author: str = ""
    notes: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": str(self.version),
            "description": self.description,
            "formula": self.formula,
            "range": self.range,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "created_at": self.created_at,
            "author": self.author,
            "notes": self.notes,
        }


@dataclass
class MetricFamily:
    """度量族定义。
    
    一个度量族包含多个相关度量，它们共享：
    - 版本号
    - 兼容性矩阵
    - 迁移规则
    """
    name: str
    version: Version
    description: str
    metrics: list[MetricDefinition] = field(default_factory=list)
    compatibility: dict[str, str] = field(default_factory=dict)  # 版本 → 兼容性描述
    migrations: dict[str, str] = field(default_factory=dict)  # 版本 → 迁移规则描述
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    author: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    def add_metric(self, metric: MetricDefinition) -> None:
        self.metrics.append(metric)
    
    def get_metric(self, name: str) -> Optional[MetricDefinition]:
        for m in self.metrics:
            if m.name == name:
                return m
        return None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": str(self.version),
            "description": self.description,
            "metrics": [m.to_dict() for m in self.metrics],
            "compatibility": self.compatibility,
            "migrations": self.migrations,
            "tags": self.tags,
            "created_at": self.created_at,
            "author": self.author,
        }


@dataclass
class CompatibilityResult:
    """兼容性检查结果。"""
    from_version: str
    to_version: str
    compatible: bool
    compatibility_level: str  # "full" | "partial" | "none"
    breaking_changes: list[str] = field(default_factory=list)
    migration_required: bool = False
    migration_notes: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# 全局度量族注册表
_REGISTRY: dict[str, MetricFamily] = {}


def get_registry() -> dict[str, MetricFamily]:
    """获取全局度量族注册表。"""
    return _REGISTRY


def register_family(family: MetricFamily) -> None:
    """注册度量族到全局注册表。"""
    _REGISTRY[family.name] = family


def unregister_family(name: str) -> Optional[MetricFamily]:
    """从注册表注销度量族。"""
    return _REGISTRY.pop(name, None)


def get_family(name: str) -> Optional[MetricFamily]:
    """从注册表获取度量族。"""
    return _REGISTRY.get(name)


def list_families() -> list[str]:
    """列出所有已注册的度量族名称。"""
    return sorted(_REGISTRY.keys())


def check_compatibility(
    family_name: str,
    from_version: str,
    to_version: str,
) -> CompatibilityResult:
    """检查度量族版本间兼容性。
    
    兼容性级别：
    - full: 完全兼容（向后兼容）
    - partial: 部分兼容（需要迁移）
    - none: 不兼容（需要完全重写）
    
    Args:
        family_name: 度量族名称
        from_version: 源版本字符串
        to_version: 目标版本字符串
    
    Returns:
        兼容性检查结果
    """
    family = get_family(family_name)
    if family is None:
        return CompatibilityResult(
            from_version=from_version,
            to_version=to_version,
            compatible=False,
            compatibility_level="none",
            breaking_changes=[f"度量族 {family_name} 未注册"],
        )
    
    fv = Version.parse(from_version)
    tv = Version.parse(to_version)
    
    # 相同版本：完全兼容
    if fv == tv:
        return CompatibilityResult(
            from_version=from_version,
            to_version=to_version,
            compatible=True,
            compatibility_level="full",
        )
    
    # 向后兼容：major 相同，minor/patch 递增
    if fv.major == tv.major and tv >= fv:
        # 检查是否有不兼容变更标记
        breaking = []
        for change in family.compatibility.get(str(tv), "").split(";"):
            if change.strip().lower().startswith("breaking"):
                breaking.append(change.strip())
        
        if breaking:
            return CompatibilityResult(
                from_version=from_version,
                to_version=to_version,
                compatible=False,
                compatibility_level="partial",
                breaking_changes=breaking,
                migration_required=True,
                migration_notes=family.migrations.get(str(tv), "无迁移说明"),
            )
        else:
            return CompatibilityResult(
                from_version=from_version,
                to_version=to_version,
                compatible=True,
                compatibility_level="full",
            )
    
    # 向前兼容：major 不同
    return CompatibilityResult(
        from_version=from_version,
        to_version=to_version,
        compatible=False,
        compatibility_level="none",
        breaking_changes=[f"major 版本不同: {fv.major} → {tv.major}"],
        migration_required=True,
        migration_notes=family.migrations.get(str(tv), "无迁移说明"),
    )


def get_migration_path(
    family_name: str,
    from_version: str,
    to_version: str,
) -> list[str]:
    """获取版本迁移路径。
    
    如果直接从 from_version 到 to_version 不兼容，
    返回中间版本列表。
    
    Args:
        family_name: 度量族名称
        from_version: 源版本字符串
        to_version: 目标版本字符串
    
    Returns:
        迁移路径列表（包含 from_version 和 to_version）
    """
    family = get_family(family_name)
    if family is None:
        return []
    
    fv = Version.parse(from_version)
    tv = Version.parse(to_version)
    
    # 收集所有已知的版本
    known_versions = set()
    for v_str in family.compatibility.keys():
        try:
            known_versions.add(Version.parse(v_str))
        except ValueError:
            pass
    
    # 简单策略：直接路径
    path = [from_version, to_version]
    
    # 如果 major 版本不同，尝试插入中间 major 版本
    if fv.major != tv.major:
        if tv.major > fv.major:
            # 向前迁移：插入中间 major 版本
            for mid_major in range(fv.major + 1, tv.major):
                mid_version = Version(mid_major)
                if mid_version in known_versions:
                    path.insert(1, str(mid_version))
        else:
            # 向后迁移：不推荐
            path = [from_version, to_version]
    
    return path


def compute_metric_fingerprint(metric: MetricDefinition) -> str:
    """计算度量的指纹（SHA-256）。
    
    基于度量的核心定义计算指纹，用于检测度量定义是否被篡改。
    
    Args:
        metric: 度量定义
    
    Returns:
        SHA-256 指纹字符串
    """
    # 排除易变字段
    core = {
        "name": metric.name,
        "version": str(metric.version),
        "formula": metric.formula,
        "dependencies": sorted(metric.dependencies),
    }
    canonical = json.dumps(core, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_family_fingerprint(family: MetricFamily) -> str:
    """计算度量族的指纹（SHA-256）。
    
    基于度量族的所有度量定义计算指纹。
    
    Args:
        family: 度量族定义
    
    Returns:
        SHA-256 指纹字符串
    """
    metrics_fingerprints = sorted(
        compute_metric_fingerprint(m) for m in family.metrics
    )
    core = {
        "name": family.name,
        "version": str(family.version),
        "metrics": metrics_fingerprints,
    }
    canonical = json.dumps(core, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def register_default_families() -> None:
    """注册项目默认的度量族。
    
    包括：
    - robustness: F4 鲁棒性度量（bridge_fraction, drop_magnitude）
    - recovery: F2 恢复度量（recovery_AUC, t_half）
    - controllability: F1 可控性度量（reachability, control_set_size）
    """
    # F4 鲁棒性度量族
    robustness_family = MetricFamily(
        name="robustness",
        version=Version(1, 0, 0),
        description="F4 鲁棒性度量：故障隔离、桥边分数、drop_magnitude",
        tags=["F4", "intervention", "bridge", "isolation"],
        compatibility={
            "1.0.0": "初始版本：drop_magnitude = (initial_signal - final_signal) / initial_signal",
            "1.1.0": "新增 bridge_fraction 度量；向后兼容",
            "2.0.0": "BREAKING: drop_magnitude 定义变更为分级隔离度量（PR-5 cell 级）",
        },
        migrations={
            "1.1.0": "bridge_fraction = n_bridge_edges / n_total_edges；与 drop_magnitude 独立",
            "2.0.0": "drop_magnitude 从全局比值改为 cell 级分级度量；需要迁移脚本",
        },
    )
    robustness_family.add_metric(MetricDefinition(
        name="drop_magnitude",
        version=Version(1, 0, 0),
        description="故障幅度：删除 k 条最高权重边后的信号下降比例",
        formula="(initial_signal - signal_after_k_removals) / initial_signal",
        range="[0, 1]",
        dependencies=[],
        tags=["F4", "intervention", "primary"],
    ))
    robustness_family.add_metric(MetricDefinition(
        name="bridge_fraction",
        version=Version(1, 1, 0),
        description="桥边分数：桥边数量占总边数的比例",
        formula="n_bridge_edges / n_total_edges",
        range="[0, 1]",
        dependencies=[],
        tags=["F4", "structure", "bridge"],
    ))
    
    # F2 恢复度量族
    recovery_family = MetricFamily(
        name="recovery",
        version=Version(1, 0, 0),
        description="F2 恢复度量：recovery_AUC、t_half、三补偿机制",
        tags=["F2", "recovery", "dynamics", "compensation"],
        compatibility={
            "1.0.0": "初始版本：recovery_AUC = normalized_area_under_recovery_curve",
            "1.1.0": "新增 t_half 度量；向后兼容",
            "2.0.0": "BREAKING: recovery_AUC 改为分位标签（C3 rank 标签）",
        },
        migrations={
            "1.1.0": "t_half = 第一个 t 使得 r(t)/drop_magnitude >= 0.5",
            "2.0.0": "recovery_AUC 从绝对阈值改为分位标签；需要重新标定",
        },
    )
    recovery_family.add_metric(MetricDefinition(
        name="recovery_AUC",
        version=Version(1, 0, 0),
        description="恢复 AUC：归一化恢复曲线下的面积",
        formula="sum_t(r(t)) / (T * drop_magnitude)",
        range="[0, 1]",
        dependencies=["drop_magnitude"],
        tags=["F2", "recovery", "primary"],
    ))
    recovery_family.add_metric(MetricDefinition(
        name="t_half",
        version=Version(1, 1, 0),
        description="半恢复时间：恢复达到 50% 的时间步",
        formula="min t such that r(t) / drop_magnitude >= 0.5",
        range="[1, T] or None",
        dependencies=["recovery_AUC", "drop_magnitude"],
        tags=["F2", "recovery", "temporal"],
    ))
    recovery_family.add_metric(MetricDefinition(
        name="tau_recovery",
        version=Version(1, 1, 0),
        description="恢复时间常数：指数恢复模型的 tau 估计",
        formula="t_half / ln(2)",
        range="[1, T] or None",
        dependencies=["t_half"],
        tags=["F2", "recovery", "temporal", "model"],
    ))
    
    # F1 可控性度量族
    controllability_family = MetricFamily(
        name="controllability",
        version=Version(1, 0, 0),
        description="F1 可控性度量：可达性、控制集大小",
        tags=["F1", "controllability", "reachability", "control"],
        compatibility={
            "1.0.0": "初始版本：reachability、control_set_size",
            "1.1.0": "新增 graded_isolation 度量；向后兼容",
        },
        migrations={
            "1.1.0": "graded_isolation: 分级隔离度量，替代二元隔离",
        },
    )
    controllability_family.add_metric(MetricDefinition(
        name="reachability",
        version=Version(1, 0, 0),
        description="可达性：从种子节点可达的节点比例",
        formula="n_reachable / n_total_nodes",
        range="[0, 1]",
        dependencies=[],
        tags=["F1", "controllability", "primary"],
    ))
    controllability_family.add_metric(MetricDefinition(
        name="control_set_size",
        version=Version(1, 0, 0),
        description="控制集大小：控制所有节点所需的最小节点集",
        formula="min |S| such that all nodes reachable from S",
        range="[1, n_nodes]",
        dependencies=[],
        tags=["F1", "controllability", "primary"],
    ))
    controllability_family.add_metric(MetricDefinition(
        name="graded_isolation",
        version=Version(1, 1, 0),
        description="分级隔离：删除桥边后的隔离度分级度量",
        formula="f(component_sizes) with graded penalty",
        range="[0, 1]",
        dependencies=["bridge_fraction"],
        tags=["F1", "controllability", "graded", "PR-5"],
    ))
    
    register_family(robustness_family)
    register_family(recovery_family)
    register_family(controllability_family)


# 模块加载时自动注册默认度量族
register_default_families()
