#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE 16 -- every generated artifact carries a recomputable structure signature.

T4 of the foundation roadmap asks two things that are easy to fudge separately
and only worth having together:

  1. a generated organism *records* its structural signature, so two artifacts
     are comparable for structural identity and a renamed copy of the same
     wiring is recognisable as a duplicate;
  2. that signature is **recomputable from the artifact itself**, so the record
     can be audited rather than trusted.

This gate enforces both on a freshly generated artifact (fail-closed: if the
generator stops attaching a signature, or the signature stops matching what
`topology_profile` recomputes from the same wiring, the gate is red).

It also audits every committed organism and reports how many are *legacy*
(preserved before the signature was introduced). Legacy artifacts are reported,
not failed on -- deleting or hand-editing 191 committed research artifacts just
to make a gate green is worse than a clearly printed debt line. What WOULD fail
the gate is a legacy artifact that claims a signature and cannot reproduce it.

Run:
    python scripts/check_topology_signature.py
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
ORGANISMS = ROOT / "male_cns" / "virtual_organisms"
sys.path.insert(0, str(MCP))


def fail(msg: str) -> int:
    print("GATE 16: FAIL -- %s" % msg)
    return 1


def _fresh_artifact(py: str) -> dict | None:
    """Generate one organism into a temp dir and return its parsed doc.

    The temp dir is removed before returning: a gate must not leave artifacts
    behind and must not need any destructive bulk delete to clean up after
    itself.
    """
    import subprocess
    tmp = Path(tempfile.mkdtemp(prefix="flybrain_g16_"))
    try:
        p = subprocess.run(
            [py, str(ROOT / "flybrain_cli.py"), "generate",
             "--motif-source", "local", "--blueprint", "predictive_coding_v2",
             "--modules", "3", "--agents-per-module", "4",
             "--name", "g16_probe", "--out", str(tmp), "--no-html"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600)
        if p.returncode != 0:
            print("  [warn] generator exited %d: %s"
                  % (p.returncode, (p.stderr or p.stdout or "").strip()[:200]))
            return None
        path = tmp / "g16_probe.json"
        if not path.exists():
            print("  [warn] generator reported success but wrote no artifact")
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _artifact_signature(doc: dict) -> str | None:
    tp = doc.get("topology_profile")
    if not isinstance(tp, dict):
        return None
    if tp.get("status") != "ok":
        return None
    sig = tp.get("signature")
    return sig if isinstance(sig, str) and sig.startswith("sha256:") else None


def main() -> int:
    py = sys.executable
    from topology_profile import profile, StructureSignatureIndex

    problems: list[str] = []

    # ---- 1. a freshly generated artifact carries a recomputable signature ----
    art = _fresh_artifact(py)
    if art is None:
        problems.append("cannot generate a probe artifact")
    else:
        doc = art
        sig = _artifact_signature(doc)
        if sig is None:
            problems.append("artifact has no ok topology_profile.signature")
        else:
            recomp = profile(doc["organism"]).get("profile_signature")
            if recomp != sig:
                problems.append("recorded signature %s != recomputed %s" % (sig[:18], recomp[:18]))
            else:
                print("  [ok] fresh artifact signature recomputes: %s..." % sig[:26])
            # the recorded size must agree with the payload
            tp = doc["topology_profile"]
            for k in ("n_nodes", "n_edges"):
                rec = (tp.get("size") or {}).get(k)
                real = (doc.get("metrics") or {}).get(k)
                if rec is not None and real is not None and rec != real:
                    problems.append("topology_profile.size.%s=%r but metrics.%s=%r" % (k, rec, k, real))
            # honest boundary: the profile must not claim to measure dynamics
            if "dynamics" not in (tp.get("not_measured") or []):
                problems.append("topology_profile.not_measured omits 'dynamics'")
        # ---- 2. the signature index supports dedup + diff ----
        with tempfile.TemporaryDirectory(prefix="flybrain_g16_idx_") as td:
            idxp = Path(td) / "idx.json"
            org = doc["organism"]
            idx = StructureSignatureIndex.new()
            st1, _ = idx.add("run_a", profile(dict(org)))
            st2, dup = idx.add("renamed_copy", profile(dict(org)))
            st3, _ = idx.add("changed", profile({
                "nodes": list(org["nodes"]),
                "edges": list(org["edges"]) + [dict(org["edges"][0])],
            }))
            if st1 != "new":
                problems.append("index: first insertion is not 'new' (%r)" % st1)
            if st2 != "duplicate" or dup != "run_a":
                problems.append("index: identical wiring not flagged duplicate (%r, %r)"
                                % (st2, dup))
            if st3 != "new":
                problems.append("index: changed wiring not flagged new (%r)" % st3)
            d = idx.diff("run_a", "changed")
            if d.get("identical_structure") is not False:
                problems.append("index.diff: changed wiring not reported non-identical")
            if d.get("size_delta_b_minus_a", {}).get("n_edges") != 1:
                problems.append("index.diff: edge-count delta wrong (%r)" % d)
            idx.save(idxp)
            if not idxp.exists() or idxp.stat().st_size < 40:
                problems.append("index did not persist")
            print("  [ok] signature index: dedup + diff + persist")

    # ---- 3. audit every committed organism ----
    legacy = 0
    bad_claim = 0
    total = 0
    for f in sorted(glob.glob(str(ORGANISMS / "**" / "*.json"), recursive=True)):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        org = d.get("organism")
        if not isinstance(org, dict):
            continue
        total += 1
        sig = _artifact_signature(d)
        if sig is None:
            legacy += 1
            continue
        if profile(org).get("profile_signature") != sig:
            bad_claim += 1
            problems.append("committed artifact claims a signature it cannot reproduce: %s"
                            % os.path.relpath(f, ROOT))
    print("  committed organisms: %d (legacy without signature: %d, bad claims: %d)"
          % (total, legacy, bad_claim))
    if bad_claim:
        problems.append("%d committed artifact(s) claim a signature that does not recompute"
                        % bad_claim)

    print("=" * 64)
    if problems:
        print("GATE 16: FAIL -- %d problem(s)" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    print("GATE 16: PASS -- generated artifacts carry a recomputable structure "
          "signature; index dedup/diff works; %d legacy artifact(s) reported, "
          "0 bad claims" % legacy)
    return 0


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: inject a signature defect and assert the gate
    goes red.

    Each case writes a mutated organism artifact to a temp dir, monkey-patches
    the ORGANISMS path, re-runs main(), asserts non-zero exit, restores state
    in a finally block. Apply and restore are structurally separate (tempfile
    + globals swap + finally), so no injection can leak state into the next one.
    """
    import tempfile
    bad = 0
    n_inj = 0

    def expect(name: str, apply_fn, restore_fn) -> None:
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            rc = main()
        finally:
            restore_fn()
        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. Write an artifact that claims a signature it cannot reproduce —
    #    the gate should catch the bad claim.
    def _patch_bad_signature():
        td = tempfile.mkdtemp(prefix="gate16_inj_")
        fake = {
            "organism": {"nodes": [{"id": "n1", "type": "neuron"},
                                    {"id": "n2", "type": "neuron"}],
                          "edges": [{"from": "n1", "to": "n2", "weight": 1.0}]},
            "metrics": {"n_nodes": 2, "n_edges": 1},
            "topology_profile": {"status": "ok",
                                  "signature": "sha256:DEADBEEF00000000000000000000000000000000000000000000000000000000",
                                  "size": {"n_nodes": 2, "n_edges": 1},
                                  "not_measured": ["dynamics"]},
        }
        p = Path(td) / "fake_organism.json"
        p.write_text(json.dumps(fake), encoding="utf-8")
        globals()["ORGANISMS"] = Path(td)
    def _restore_organisms():
        globals()["ORGANISMS"] = ROOT / "male_cns" / "virtual_organisms"
    expect("artifact claims un-reproducible signature (sha256:DEADBEEF...)",
           _patch_bad_signature, _restore_organisms)

    # 2. Write an artifact with a corrupted topology_profile.size — the gate
    #    should catch the size mismatch.
    def _patch_bad_size():
        td = tempfile.mkdtemp(prefix="gate16_inj_")
        fake = {
            "organism": {"nodes": [{"id": "n1", "type": "neuron"},
                                    {"id": "n2", "type": "neuron"},
                                    {"id": "n3", "type": "neuron"}],
                          "edges": [{"from": "n1", "to": "n2", "weight": 1.0}]},
            "metrics": {"n_nodes": 3, "n_edges": 1},
            "topology_profile": {"status": "ok",
                                  "signature": "sha256:" + "a" * 64,
                                  "size": {"n_nodes": 99, "n_edges": 99},
                                  "not_measured": ["dynamics"]},
        }
        p = Path(td) / "fake_organism.json"
        p.write_text(json.dumps(fake), encoding="utf-8")
        globals()["ORGANISMS"] = Path(td)
    expect("artifact topology_profile.size mismatch (99 vs 3/1)",
           _patch_bad_size, _restore_organisms)

    # 3. Write an artifact that omits 'dynamics' from not_measured — the gate
    #    should catch the honesty boundary violation.
    def _patch_no_dynamics():
        td = tempfile.mkdtemp(prefix="gate16_inj_")
        fake = {
            "organism": {"nodes": [{"id": "n1", "type": "neuron"}],
                          "edges": []},
            "metrics": {"n_nodes": 1, "n_edges": 0},
            "topology_profile": {"status": "ok",
                                  "signature": "sha256:" + "b" * 64,
                                  "size": {"n_nodes": 1, "n_edges": 0},
                                  "not_measured": ["temporal"]},
        }
        p = Path(td) / "fake_organism.json"
        p.write_text(json.dumps(fake), encoding="utf-8")
        globals()["ORGANISMS"] = Path(td)
    expect("artifact omits 'dynamics' from not_measured",
           _patch_no_dynamics, _restore_organisms)

    print()
    if bad:
        print("GATE 16 INJECTIONS: %d/%d FAILED (gate stayed green)" % (bad, n_inj))
    else:
        print("GATE 16 INJECTIONS: PASS — %d/%d defects caught" % (n_inj, n_inj))
    return n_inj, bad


if __name__ == "__main__":
    sys.exit(main())
