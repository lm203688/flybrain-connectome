"""selfverify — preregistration as an executable gate.

Public API:
    Protocol            parse a preregistration record
    Verdict             the four first-class outcomes
    check               run the gate (independent recomputation)
    independent_recompute
    evaluate_rejection  PR-2b-style pre-execution rejection
    blueprint.build     S1 命题图（Blueprint IR）构建
    blueprint.validate  S1 命题图验证
    receipt.issue_one   S2 验证收据生成
    receipt.verify_one  S2 验证收据验证
    redteam             S3 红队自验证套件
    dynamics.compute_all    S3 最小动力学读出
    dynamics.recovery_auc   恢复 AUC 度量
    dynamics.tau_recovery   恢复时间常数估计
"""
from .protocol import Protocol, Verdict
from .gate import check, independent_recompute
from .prerejection import evaluate_rejection
from .blueprint import build as blueprint_build, validate as blueprint_validate
from .receipt import issue_one as receipt_issue_one, verify_one as receipt_verify_one
from .dynamics import compute_all as dynamics_compute_all, recovery_auc, tau_recovery

__all__ = [
    "Protocol",
    "Verdict",
    "check",
    "independent_recompute",
    "evaluate_rejection",
    "blueprint_build",
    "blueprint_validate",
    "receipt_issue_one",
    "receipt_verify_one",
    "dynamics_compute_all",
    "recovery_auc",
    "tau_recovery",
]
__version__ = "0.3.0"
