"""selfverify — preregistration as an executable gate.

Public API:
    Protocol            parse a preregistration record
    Verdict             the four first-class outcomes
    check               run the gate (independent recomputation)
    independent_recompute
    evaluate_rejection  PR-2b-style pre-execution rejection
"""
from .protocol import Protocol, Verdict
from .gate import check, independent_recompute
from .prerejection import evaluate_rejection

__all__ = [
    "Protocol",
    "Verdict",
    "check",
    "independent_recompute",
    "evaluate_rejection",
]
__version__ = "0.1.0"
