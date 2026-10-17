"""
Gate 15: the topology-aware layer is self-consistent and honest.

WHY THIS GATE EXISTS
--------------------
`topology_profile.py` turns one-off structural measurements (spectral radius,
modularity, feedback fraction, motif census) into a reusable capability. A
capability is only a capability if it is *checked* — so this gate pins the
layer's semantics and refuses to let it drift silently.

It is deliberately narrow and dependency-free. It does NOT re-derive the
numbers from first principles (the module's own ``--selftest`` does that); it
asserts the *contract* the rest of the toolkit will rely on:

  1. the module's own self-test passes (exit 0)
  2. the spectral radius is real, not a constant: rho of a weighted 2-cycle
     equals the weight, and rho changes when the weight changes
  3. DAG-ness is detected (a chain has zero feedback arcs)
  4. the structural signature is deterministic and change-sensitive
  5. the honesty contract holds: ``not_measured`` is present, non-empty and
     names ``dynamics`` — a structural profile may never imply a functional one
  6. the CLI surface works: profiling a written organism returns valid JSON
     with the required top-level keys

Injected-defect behaviour (this is the discipline the repo requires): zeroing
the spectral radius, dropping ``not_measured``, or making the signature
order-dependent each make this gate FAIL.

Exit code 0 on pass, 1 on fail. Stdlib only; runs offline in --quick.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "flybrain-connectome-mcp"
MODULE = MCP / "topology_profile.py"

REQUIRED_KEYS = {
    "schema_version", "kind", "source", "size", "degree", "reciprocity",
    "components", "modularity_q", "clustering_transitivity",
    "spectral_radius", "feedback_edge_fraction", "motifs",
    "inhibition_ratio", "not_measured", "caveat", "profile_signature",
}

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name,
                            ("- " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def main() -> int:
    print("=" * 72)
    print("GATE 15 - topology profile layer is self-consistent and honest")
    print("=" * 72)

    if not MODULE.exists():
        print("  [FAIL] topology_profile.py present - %s" % MODULE)
        print("GATE 15: FAIL - module missing")
        return 1
    check("module present", True, MODULE.name)

    py = sys.executable

    # -- 1. the module's own self-test -------------------------------------
    print("\n-- 1. module self-test --")
    p = subprocess.run([py, str(MODULE), "--selftest"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    tail = (p.stdout or "").strip().splitlines()
    check("--selftest exits 0", p.returncode == 0,
          (tail[-1] if tail else "no output"))
    check("--selftest reports PASS", "PASS" in (p.stdout or ""))

    # -- 2..6 import the module and assert the contract ---------------------
    print("\n-- 2. structural contract (imported directly) --")
    sys.path.insert(0, str(MCP))
    try:
        import topology_profile as tp  # type: ignore
    except Exception as e:  # noqa: BLE001
        check("import topology_profile", False, repr(e))
        print("GATE 15: FAIL")
        return 1
    check("import topology_profile", True)

    # rho of a weighted 2-cycle equals the weight (real, not constant)
    def two_cycle(w):
        return {"nodes": [{"id": "1"}, {"id": "2"}],
                "edges": [{"from": "1", "to": "2", "weight": w},
                          {"from": "2", "to": "1", "weight": w}]}

    rho3 = tp.profile(two_cycle(3.0))["spectral_radius"]
    rho7 = tp.profile(two_cycle(7.0))["spectral_radius"]
    check("rho == weight (3.0)", abs(rho3 - 3.0) < 1e-6, str(rho3))
    check("rho is not a constant", abs(rho7 - rho3) > 1.0,
          "rho(3)=%s rho(7)=%s" % (rho3, rho7))

    # DAG detection
    chain = {"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
             "edges": [{"from": "1", "to": "2"}, {"from": "2", "to": "3"}]}
    check("chain feedback == 0", abs(tp.profile(chain)["feedback_edge_fraction"]) < 1e-12)

    # signature: deterministic + change-sensitive
    sig_a = tp.profile(chain)["profile_signature"]
    sig_b = tp.profile({"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                        "edges": [{"from": "1", "to": "2"},
                                  {"from": "2", "to": "3"}]})["profile_signature"]
    cyc = {"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
           "edges": [{"from": "1", "to": "2"}, {"from": "2", "to": "3"},
                     {"from": "3", "to": "1"}]}
    check("signature deterministic", sig_a == sig_b, sig_a[:26])
    check("signature change-sensitive",
          sig_a != tp.profile(cyc)["profile_signature"])

    # honesty contract
    nm = tp.profile(chain).get("not_measured")
    check("not_measured present and non-empty", bool(nm), str(nm))
    check("not_measured names dynamics", bool(nm) and "dynamics" in nm)
    check("caveat present", bool(tp.profile(chain).get("caveat")))

    # -- 3. CLI surface -----------------------------------------------------
    print("\n-- 3. CLI surface --")
    with tempfile.TemporaryDirectory(prefix="flybrain_gate15_") as tmp:
        org = Path(tmp) / "org.json"
        org.write_text(json.dumps({
            "schema_version": "1.2.1",
            "blueprint": "gate15_fixture",
            "organism": {
                "nodes": [{"id": "m0_rep", "role": "tissue_rep", "module": 0},
                          {"id": "m0_a0", "role": "cell", "module": 0},
                          {"id": "m1_rep", "role": "tissue_rep", "module": 1},
                          {"id": "m1_a0", "role": "cell", "module": 1}],
                "edges": [{"from": "m0_rep", "to": "m0_a0", "weight": 0.5,
                           "kind": "recurrent"},
                          {"from": "m1_rep", "to": "m1_a0", "weight": 0.5,
                           "kind": "recurrent"}],
            },
        }), encoding="utf-8")
        q = subprocess.run([py, str(MODULE), str(org), "--json"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT))
        check("CLI --json exits 0", q.returncode == 0, (q.stderr or "").strip()[:80])
        try:
            doc = json.loads(q.stdout)
            check("CLI --json is valid JSON", True)
            missing = sorted(REQUIRED_KEYS - set(doc))
            check("profile has all required keys", not missing, str(missing))
            check("profile.kind is topology_profile",
                  doc.get("kind") == "topology_profile")
        except Exception as e:  # noqa: BLE001
            check("CLI --json is valid JSON", False, repr(e))

    print("=" * 72)
    if failures:
        print("GATE 15: FAIL - %s" % ", ".join(failures))
        return 1
    print("GATE 15: PASS - topology layer self-consistent and honest")
    return 0


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: inject defects into the topology_profile
    module and assert the gate goes red. Each injection exercises one of
    the failure classes the gate's docstring declares.

    Apply and restore are structurally separate (monkey-patch + finally),
    so no injection leaks state into the next one.
    """
    import sys as _sys
    bad = 0
    n_inj = 0

    # Load the module for monkey-patching
    sys.path.insert(0, str(MCP))
    import topology_profile as tp

    real_profile = tp.profile

    def expect(name, apply_fn, restore_fn):
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            rc = main()
        finally:
            restore_fn()
            failures.clear()
        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. Zero out the spectral radius (constant, not real).
    def _inj_zero_rho():
        def _patched(org):
            result = real_profile(org)
            result["spectral_radius"] = 0.0
            return result
        tp.profile = _patched

    expect("the spectral radius is zeroed (constant, not real)",
           _inj_zero_rho,
           lambda: setattr(tp, "profile", real_profile))

    # 2. Drop the not_measured honesty field.
    def _inj_drop_nm():
        def _patched(org):
            result = real_profile(org)
            result.pop("not_measured", None)
            return result
        tp.profile = _patched

    expect("the not_measured honesty field is dropped",
           _inj_drop_nm,
           lambda: setattr(tp, "profile", real_profile))

    # 3. Make the signature non-deterministic (different each call).
    def _inj_nondeterministic_sig():
        # An incrementing call counter, NOT time.time_ns(). On Windows the
        # clock resolution (~100 ns) makes two back-to-back calls return the
        # SAME timestamp, so a clock-stamped signature is identical on the
        # two calls the determinism check compares -- the injection never
        # turned the gate red (the "1/5 injections did not turn red" bug).
        # A counter is unique by construction and needs no clock resolution.
        call = [0]

        def _patched(org):
            result = real_profile(org)
            call[0] += 1
            result["profile_signature"] = result["profile_signature"] + "_call_%d" % call[0]
            return result
        tp.profile = _patched

    expect("the signature is non-deterministic (differs per call)",
           _inj_nondeterministic_sig,
           lambda: setattr(tp, "profile", real_profile))

    # 4. Drop the caveat field.
    def _inj_drop_caveat():
        def _patched(org):
            result = real_profile(org)
            result["caveat"] = ""
            return result
        tp.profile = _patched

    expect("the caveat field is emptied",
           _inj_drop_caveat,
           lambda: setattr(tp, "profile", real_profile))

    # 5. Make chain feedback non-zero (break DAG detection).
    def _inj_bad_feedback():
        def _patched(org):
            result = real_profile(org)
            result["feedback_edge_fraction"] = 0.5
            return result
        tp.profile = _patched

    expect("chain feedback is made non-zero (DAG detection broken)",
           _inj_bad_feedback,
           lambda: setattr(tp, "profile", real_profile))

    # State must be byte-clean after the battery.
    assert tp.profile is real_profile, "injections leaked tp.profile"
    assert failures == [], "injections leaked failures list"

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"GATE 15: FAIL -- {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    sys.exit(_run_with_injections())
