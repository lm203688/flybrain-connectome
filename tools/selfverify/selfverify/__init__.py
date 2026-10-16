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
"""
from .protocol import Protocol, Verdict
from .gate import check, independent_recompute
from .prerejection import evaluate_rejection
from .blueprint import build as blueprint_build, validate as blueprint_validate
from .receipt import issue_one as receipt_issue_one, verify_one as receipt_verify_one

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
]
__version__ = "0.2.0"
