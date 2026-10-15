"""Command-line interface: `selfverify check --protocol ... --results ...`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .gate import check
from .prerejection import evaluate_rejection
from .protocol import Protocol, Verdict


def _build_report(protocol: Protocol, results: dict) -> dict:
    gate = check(protocol, results)
    return {
        "protocol_id": protocol.id,
        "hypothesis": protocol.hypothesis,
        "metric": protocol.metric,
        "verdict": gate["verdict"],
        "evidence": gate["evidence"],
        "rejection_rules": evaluate_rejection(protocol, results),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="selfverify",
        description="Preregistration as an executable gate (independent recomputation).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="run a preregistered gate on a results file")
    c.add_argument("--protocol", required=True, help="path to protocol JSON")
    c.add_argument("--results", required=True, help="path to results JSON")
    c.add_argument("--json", action="store_true", help="emit full JSON report")
    c.add_argument("--report-path", default="", help="optional path to write the JSON report")

    args = parser.parse_args(argv)

    protocol = Protocol.load(args.protocol)
    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    report = _build_report(protocol, results)

    if args.report_path:
        Path(args.report_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[{report['protocol_id']}] verdict = {report['verdict']}")
        print(json.dumps(report["evidence"], ensure_ascii=False, indent=2))
        if report["rejection_rules"]:
            print("rejection_rules:", json.dumps(report["rejection_rules"], ensure_ascii=False))

    # Exit non-zero only on FAILURE (a real negative), not on WEAK or rejection.
    return 1 if report["verdict"] == Verdict.FAILURE.value else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
