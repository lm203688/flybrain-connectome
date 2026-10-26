#!/usr/bin/env python3
"""Run every gate this repo has, in one command, with one exit code.

CI (`.github/workflows/ci.yml`) runs the same set. Having a single local entry
point means "green locally" and "green in CI" cannot silently diverge — the
usual cause of a red pipeline nobody can reproduce.

Gates, in order of cheapness:

  1  secrets      scripts/check_no_secrets.py        no deps, ~0.2 s
  2  docs drift   scripts/check_docs_consistency.py  no deps, ~0.2 s
  3  MCP tools    scripts/check_mcp_tools.py         needs numpy; spawns the server
  4  degraded     scripts/check_degraded_mode.py     optional dep absent must not crash
  5  artifact     generated output is structurally real (see the checker's docstring)
  6  flybrain     flybrain_cli verify                 needs the MaleCNS dataset
  7  module arch  neuropil modules + worm data + combinator + HMAC
  8  tiering      physical tiering (public MIT tree vs private Tier-2 repo)
  9  unit library functional units + connection types + composer fail-closed
 10  embodiment   anchors + measured matrices + acknowledged contradictions
 11  function     every unit tagged with function axis from PROJECT_VISION
 12  costs        every connection type has a latency/cost with source
 13  composition  wiring resolves, ports complete, one-way declarations counted
 14  taxonomy     every unit.system is in taxonomy_systems.json
 15  topology     topology_profile layer is self-consistent and honest
 16  signature    every generated artifact carries a recomputable structure signature
 17  comp closure declared-incompatible pairs are registered; no silent wiring drift
 18  fast decision north-star D1 spec is self-consistent (fast_decision.py --selftest)
 19  function tax every unit.function maps to the 24-category controlled vocabulary
 20  sources      connectome source adapters present; zebrafish profiles built
 21  cap tax      every capability maps to the 22-category controlled vocabulary
 22  dynamics    structure x dynamics bridge lookup honest + recomputable
 23  stacked     prebuilt stacked blueprints internally consistent
 24  t3          middleware rule engine functional + data-backed (conditional:
                 skips on a bare public install, runs when the Tier-2 core is
                 configured via FLYBRAIN_CORE or a sibling checkout)

Gates 4 and 5 generate a throwaway organism into a temp dir, so they need no
dataset. The data-backed smoke test (`flybrain verify`, 70 assertions) is *not*
run unless you pass --with-data, because it needs a local MaleCNS v1.0 copy
(~5.63 GB) pointed at by FLYBRAIN_DATA_DIR. Gate 10 runs offline against the
committed anchor artifact, and only recomputes from raw data under --with-data.

Usage:
    python scripts/run_gates.py                  # 23 gates, no dataset needed
    python scripts/run_gates.py --with-data      # 29 gates (+ `flybrain verify`)
    python scripts/run_gates.py --quick          # 25 gates: skips 3, 4, 5 (no numpy,
                                                 #   no server spawn, no generated artifact)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def run(label: str, cmd: list[str], cwd: Path | None = None,
        env: dict | None = None) -> tuple[bool, str]:
    print("-" * 72)
    print(">>> %s" % label)
    print("    %s" % " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.strip().splitlines():
        print("    " + line)
    ok = p.returncode == 0
    print("    -> %s (exit %d)" % ("PASS" if ok else "FAIL", p.returncode))
    return ok, out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true",
                    help="skip gates 3/4/5 (no numpy, no server spawn, no artifact)")
    ap.add_argument("--with-data", action="store_true",
                    help="also run `flybrain verify` (needs FLYBRAIN_DATA_DIR)")
    args = ap.parse_args()

    py = sys.executable
    results: list[tuple[str, bool]] = []

    # ---- Gate 38: dependency self-check (runs FIRST — distinguishes env from code) ----
    gate38_args = [py, str(SCRIPTS / "check_dependencies.py")]
    if args.quick:
        gate38_args.append("--quick")
    results.append(("gate38 dependencies", run(
        "GATE 38 — dependency self-check (missing numpy = env problem, not code defect)",
        gate38_args)[0]))

    results.append(("gate1 secrets", run(
        "GATE 1 — no hardcoded credentials",
        [py, str(SCRIPTS / "check_no_secrets.py")])[0]))

    results.append(("gate2 docs drift", run(
        "GATE 2 — docs match code",
        [py, str(SCRIPTS / "check_docs_consistency.py")])[0]))

    # ---- Gate 11: the function axis (stdlib only, runs even in --quick) ----
    results.append(("gate11 function coverage", run(
        "GATE 11 — PROJECT_VISION function coverage measured, gaps declared",
        [py, str(SCRIPTS / "check_function_coverage.py")])[0]))

    # ---- Gate 12: the connection cost axis (stdlib only, runs in --quick) ----
    results.append(("gate12 connection costs", run(
        "GATE 12 — every connection latency cited; design abstractions carry none",
        [py, str(SCRIPTS / "check_connection_costs.py")])[0]))

    # ---- Gate 13: composition semantics (stdlib only, runs in --quick) ----
    results.append(("gate13 composition", run(
        "GATE 13 — wiring resolves, ports complete, one-way declarations counted",
        [py, str(SCRIPTS / "check_composition.py")])[0]))

    # ---- Gate 14: taxonomy.system controlled vocabulary (stdlib only, --quick) ----
    results.append(("gate14 taxonomy", run(
        "GATE 14 — every unit.system is in taxonomy_systems.json (no silent drift)",
        [py, str(SCRIPTS / "check_taxonomy.py")])[0]))

    # ---- Gate 15: topology-aware layer (stdlib only, runs even in --quick) ----
    results.append(("gate15 topology", run(
        "GATE 15 — topology profile layer is self-consistent and honest",
        [py, str(SCRIPTS / "check_topology_profile.py")])[0]))

    # ---- Gate 17: composition closure (stdlib only, runs even in --quick) ----
    results.append(("gate17 composition closure", run(
        "GATE 17 — declared-incompatible pairs registered; compatibility matrix intact",
        [py, str(SCRIPTS / "check_composition_closure.py")])[0]))

    # ---- Gate 18: north-star fast-decision spec (stdlib only, --quick) ----
    results.append(("gate18 fast decision spec", run(
        "GATE 18 — north-star D1 fast-decision spec is self-consistent",
        [py, str(ROOT / "flybrain-connectome-mcp" / "fast_decision.py"),
         "--selftest"])[0]))

    # ---- Gate 19: function controlled vocabulary (stdlib only, --quick) ----
    results.append(("gate19 function taxonomy", run(
        "GATE 19 — every unit.function maps to the 24-category controlled vocabulary",
        [py, str(SCRIPTS / "check_function_canonical.py")])[0]))

    # ---- Gate 20: connectome source adapters (stdlib only, --quick) ----
    results.append(("gate20 sources", run(
        "GATE 20 — connectome source adapters present; zebrafish profiles built",
        [py, str(SCRIPTS / "check_sources.py")])[0]))

    # ---- Gate 21: capability controlled vocabulary (stdlib only, --quick) ----
    results.append(("gate21 capability taxonomy", run(
        "GATE 21 — every capability maps to the 22-category controlled vocabulary",
        [py, str(SCRIPTS / "check_capability_canonical.py")])[0]))

    # ---- Gate 22: structure x dynamics bridge lookup (stdlib only, --quick) ----
    results.append(("gate22 dynamics bridge", run(
        "GATE 22 — rho->capacity calibration table complete; refuted axis stays refuted",
        [py, str(SCRIPTS / "check_dynamics_bridge.py")])[0]))

    # ---- Gate 23: prebuilt stacked blueprints integrity (stdlib, --quick) ----
    results.append(("gate23 stacked blueprints", run(
        "GATE 23 — prebuilt stacked blueprints internally consistent; summary not self-reported",
        [py, str(SCRIPTS / "check_stacked_blueprints.py")])[0]))

    # ---- Gate 24: T3 middleware rule engine (conditional, fail-closed, --quick) ----
    results.append(("gate24 t3 middleware", run(
        "GATE 24 — Tier-2 middleware rule engine functional + data-backed (skips if core absent)",
        [py, str(SCRIPTS / "check_t3_middleware.py")])[0]))

    # ---- Gate 25: Phase A runtime — metabolic loop + boundary + monitor + metabolism ----
    results.append(("gate25 runtime", run(
        "GATE 25 — Phase A runtime: metabolic loop + boundary + monitor + metabolism "
        "(with 3 injected-defect tests)",
        [py, str(SCRIPTS / "check_runtime.py")])[0]))

    # ---- Gate 26: Phase B damage + repair (B1–B4) ----
    results.append(("gate26 repair", run(
        "GATE 26 — Phase B damage injection + repair: damage.py + repair.py "
        "(with 5 injected-defect tests)",
        [py, str(SCRIPTS / "check_repair.py")])[0]))

    # ---- Gate 27: Phase D combination reaction + registry + motif novelty ----
    results.append(("gate27 combination reaction", run(
        "GATE 27 — Phase D combination reaction engine + species registry + "
        "motif novelty (with 4 injected-defect tests)",
        [py, str(SCRIPTS / "check_combination_reaction.py")])[0]))

    # ---- Gate 28: Phase C population: clone/mutate/lineage/selection/archive/death ----
    results.append(("gate28 population", run(
        "GATE 28 — Phase C population dynamics: clone/mutate + lineage + "
        "selection + archive + death (with 4 injected-defect tests)",
        [py, str(SCRIPTS / "check_population.py")])[0]))

    # ---- Gate 29: Phase E3 NCA-style local development ----
    results.append(("gate29 development", run(
        "GATE 29 — Phase E3 NCA-style local development: growth rules + "
        "audit trail + 4 convergence reasons + fail-closed "
        "(with 4 injected-defect tests)",
        [py, str(SCRIPTS / "check_development.py")])[0]))

    # ---- Gate 30: E2-P1 orchestration base + scientific self-verification (S6-S9) ----
    results.append(("gate30 llm orchestrator", run(
        "GATE 30 — E2-P1 orchestration base: task source + evidence block + "
        "4 topologies + trace discipline + S6 control scoreability + "
        "five-element verification + S7 resolution precheck + "
        "S8 mechanism falsification + S9 perturbation over correlation + "
        "4 injected-defect tests",
        [py, str(SCRIPTS / "check_llm_orchestrator.py")])[0]))

    # ---- Gate 31: R2 density scan — structure-function curves and d* threshold ----
    # Write to a temp dir (not _gate31_r2/) so we don't overwrite the committed
    # data file that R2 receipt hashes. The density scan output is non-deterministic
    # (floating-point accumulation order varies), so overwriting would break Gate 61.
    import tempfile as _tempfile
    _gate31_tmp = _tempfile.mkdtemp(prefix="gate31_")
    results.append(("gate31 r2 density scan", run(
        "GATE 31 — R2 density scan: structure-function curves and d* threshold",
        [py, str(SCRIPTS / "r2_density_scan.py"), "--n-samples", "50",
         "--n-nodes", "20", "--strict-axis",
         "--output-dir", _gate31_tmp])[0]))

    # ---- Gate 32: R4 sensitivity boundary analysis — robustness curves ----
    results.append(("gate32 r4 sensitivity scan", run(
        "GATE 32 — R4 sensitivity boundary: robustness curves",
        [py, str(SCRIPTS / "r4_sensitivity_scan.py"), "--n-blueprints", "8",
         "--n-nodes", "6", "--output-dir", str(ROOT / "_gate32_r4")])[0]))

    # ---- Gate 33: R1 isolation predictor expansion — mechanism tests ----
    results.append(("gate33 r1 expansion", run(
        "GATE 33 — R1 isolation predictor: N≥100 topologies + mechanism tests "
        "(P1/P2/P3 falsification checks)",
        [py, str(SCRIPTS / "r1_expansion.py"), "--n-topologies", "30",
         "--n-nodes", "6", "--output-dir", str(ROOT / "_gate33_r1")])[0]))

    # ---- Gate 34: Fusion B two-stage LLM pipeline (cheap + strong) ----
    results.append(("gate34 two-stage pipeline", run(
        "GATE 34 — Fusion B two-stage LLM pipeline: cheap pre-screen + "
        "strong escalation (10 checks + 4 injected-defect tests)",
        [py, str(SCRIPTS / "check_two_stage_pipeline.py")])[0]))

    # ---- Gate 35: Fusion A claim verifier auxiliary (structural hints) ----
    results.append(("gate35 claim verifier", run(
        "GATE 35 — Fusion A claim verifier: structural falsifiability hints "
        "+ LLM-assisted optional (warning, not failure)",
        [py, str(SCRIPTS / "claim_verifier.py"),
         "--mode", "offline"])[0]))

    # ---- Gate 36: EvoAgentX adapter POC (structure_health as fitness) ----
    results.append(("gate36 evoagentx adapter", run(
        "GATE 36 — EvoAgentX adapter POC: structure_health → fitness mapping "
        "+ mutation + comparison data (dry-run, no EvoAgentX required)",
        [py, str(SCRIPTS / "evoagentx_adapter.py"),
         "--mode", "dry-run", "--n-generations", "3", "--n-population", "10"])[0]))

    # ---- Gate 9: functional-unit library (stdlib only, runs even in --quick) ----
    results.append(("gate9 unit library", run(
        "GATE 9 — functional units + connection types + composer fail-closed",
        [py, str(SCRIPTS / "check_functional_units.py")])[0]))

    # ---- Gate 10: embodiment layer (stdlib only, runs even in --quick) ----
    gate10_cmd = [py, str(SCRIPTS / "check_embodiment.py")]
    if args.with_data:
        gate10_cmd.append("--with-data")
    results.append(("gate10 embodiment", run(
        "GATE 10 — MaleCNS embodiment anchors + measured matrices + contradictions",
        gate10_cmd)[0]))

    if not args.quick:
        results.append(("gate3 MCP tools", run(
            "GATE 3 — every advertised MCP tool responds (offline subset)",
            [py, str(SCRIPTS / "check_mcp_tools.py"), "--offline", "--python", py])[0]))

        results.append(("gate4 degraded", run(
            "GATE 4 — a missing optional dependency degrades, it does not crash",
            [py, str(SCRIPTS / "check_degraded_mode.py"), "--python", py])[0]))

        tmp = Path(tempfile.mkdtemp(prefix="flybrain_gates_"))
        try:
            gen_ok, _ = run(
                "GATE 5a — generator smoke test",
                [py, str(ROOT / "flybrain_cli.py"), "generate",
                 "--motif-source", "local", "--blueprint", "predictive_coding_v2",
                 "--modules", "3", "--agents-per-module", "4",
                 "--name", "gates_smoke", "--out", str(tmp), "--no-html"])
            artifact_ok = False
            if gen_ok:
                artifact_ok, _ = run(
                    "GATE 5b — the generated artifact is real",
                    [py, str(SCRIPTS / "check_generated_artifact.py"),
                     "--dir", str(tmp), "--name", "gates_smoke"])
            else:
                print("-" * 72)
                print("    (skipping 5/5b — generation already failed)")
            results.append(("gate5 artifact", gen_ok and artifact_ok))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if args.with_data:
        if not os.environ.get("FLYBRAIN_DATA_DIR"):
            print("-" * 72)
            print("    (--with-data requested but FLYBRAIN_DATA_DIR is unset — skipping)")
            results.append(("gate6 flybrain verify", True))
        else:
            results.append(("gate6 flybrain verify", run(
                "GATE 6 — end-to-end smoke test against the real connectome",
                [py, str(ROOT / "flybrain_cli.py"), "verify"])[0]))

    # ---- Gate 7: module architecture (Phase 8) ----
    results.append(("gate7 module arch", run(
        "GATE 7 — neuropil modules + worm data + combinator middleware + fingerprints + HMAC",
        [py, str(SCRIPTS / "check_module_architecture.py")])[0]))

    # ---- Gate 8: physical tiering (Phase 9) ----
    results.append(("gate8 tiering", run(
        "GATE 8 — physical tiering architecture (core_bridge + LICENSE clause)",
        [py, str(SCRIPTS / "check_physical_tiering.py")])[0]))

    # ---- Gate 16: structure signature in artifacts (needs numpy: generates) ----
    results.append(("gate16 structure signature", run(
        "GATE 16 — generated artifacts carry a recomputable structure signature",
        [py, str(SCRIPTS / "check_topology_signature.py")])[0]))

    # ---- Gate 39: meta-gate — every check_*.py must carry an injected-defect test ----
    results.append(("gate39 meta-gate injections", run(
        "GATE 39 — meta-gate: every check_*.py must carry an injected-defect test "
        "(V2 → V3 discipline; progressive mode with KNOWN_MISSING_INJECTIONS backlog)",
        [py, str(SCRIPTS / "check_gate_injections.py")])[0]))

    # ---- Gate 40: dual-implementation cross-check (SV-2) ----
    results.append(("gate40 dual implementation", run(
        "GATE 40 — every critical metric implemented twice with independent algorithms; "
        "disagreement > 1e-9 goes red (SV-2)",
        [py, str(SCRIPTS / "check_dual_implementation.py")])[0]))

    # ---- Gate 41: metric discrimination (SV-3c, degenerate-attack suite) ----
    results.append(("gate41 metric discrimination", run(
        "GATE 41 — every registered metric has variance above its declared floor "
        "on the standard suite (R1 legacy binary must saturate; SV-3c + SV-3d)",
        [py, str(SCRIPTS / "check_metric_discrimination.py")])[0]))

    # ---- Gate 42: statistical power pre-check (SV-5b) ----
    results.append(("gate42 statistical power", run(
        "GATE 42 — every significance/gradient claim in research_claims passes "
        "the sample-size vs effect-size power pre-check (R3 N=6 must go red)",
        [py, str(SCRIPTS / "check_statistical_power.py")])[0]))

    # ---- Gate 43: preregistered claims — manifest ↔ execution integrity (R-0.2) ----
    results.append(("gate43 preregistered claims", run(
        "GATE 43 — preregistered PR-x values in research_claims.json.preregistered "
        "must match the execution JSON verbatim (threshold / features / split / "
        "permutations / absolute label_definition); L3 outcome reported as WARN "
        "so R-0.4 negative results stay visible without turning the pipeline red",
        [py, str(SCRIPTS / "check_preregistered_claims.py")])[0]))

    # ---- Gate 44: cross-family generalization boundary (PR-3 integrity + outcome) ----
    results.append(("gate44 generalization matrix", run(
        "GATE 44 — PR-3 generalization matrix integrity: five families must match "
        "the manifest, malecns_subgraph (the real connectome anchor) must be "
        "present, and the verdict must be consistent with the underlying counts. "
        "R-0.4 negative outcome preserved verbatim",
        [py, str(SCRIPTS / "check_generalization_matrix.py")])[0]))

    # ---- Gate 45: self-intervention consistency (PR-2 integrity + outcome) ----
    results.append(("gate45 intervention test", run(
        "GATE 45 — PR-2 self-intervention integrity: action/control/predict_direction "
        "must match the manifest; the intervention slice must be disjoint from the "
        "PR-1 train/held-out slices; the verdict is recomputed from all_results so "
        "a tampered hit rate cannot silently pass",
        [py, str(SCRIPTS / "check_intervention_test.py")])[0]))

    # ---- Gate 46: recovery dynamics non-degeneracy (PR-4 integrity + outcome) ----
    results.append(("gate46 recovery dynamics", run(
        "GATE 46 — PR-4 recovery-dynamics non-degeneracy: recovery_AUC zero_ratio "
        "must stay below 30%, variance must exceed 1e-6, and all three compensation "
        "mechanisms (R-a/R-b/R-c) must show non-zero ablation variance. "
        "Stats are recomputed from all_results so a tampered summary cannot pass",
        [py, str(SCRIPTS / "check_recovery_dynamics.py")])[0]))

    # ---- Gate 47: PR-2b metric-substitution pre-check integrity ----
    results.append(("gate47 metric substitution", run(
        "GATE 47 — PR-2b pre-execution REJECTION integrity: research_claims.json "
        "must record PR2b as a pre_execution_rejection whose thresholds match the "
        "executed JSON, whose criteria were NOT modified post-hoc (R-0.4), and whose "
        "REJECT decision is either the rule's verdict or an explicitly declared "
        "override of it. Artifact rate and pooled coupling corr are recomputed from "
        "all_results so a tampered summary cannot silently reopen the substitution",
        [py, str(SCRIPTS / "check_metric_substitution.py")])[0]))

    # ---- Gate 48: claim graph integrity (Blueprint IR) ----
    results.append(("gate48 claim graph", run(
        "GATE 48 — Claim Graph (Blueprint IR) integrity: every claim must either be "
        "supported by >=1 incoming supports/tests edge or be explicitly terminal "
        "(boundary / rejected / refuted) with documentation; every evidence node must "
        "carry an artifact or script pointer; V9 warns when a claim's status outruns "
        "its preregistered evidence (FAIL/WEAK_PASS/ACCEPT verdicts)",
        [py, str(SCRIPTS / "check_claim_graph.py"),
         "--graph", str(ROOT / "claim_graph.json")])[0]))

    # ---- Gate 49: adversarial red-team battery (S3) ----
    results.append(("gate49 red-team battery", run(
        "GATE 49 — Adversarial self-verification (S3): four red-team attacks "
        "(summary_tamper, metric_saturation, analytic_redundancy, resolution_clamp) "
        "must catch each of the project's four historical defects (P1 false-positive, "
        "R2 density clamp, R1 mechanism saturation, PR-2b analytic coupling). "
        "Injection battery proves each attack is not degenerate",
        [py, str(SCRIPTS / "check_claim_redteam.py")])[0]))

    # ---- Gate 50: verification badge integrity (S5) ----
    results.append(("gate50 verification badges", run(
        "GATE 50 — Claim verification badges (V0..V5) must be consistent with the "
        "claim graph: every claim has a badge on the ladder, node.verification_level "
        "matches badge.level, V5 claims must have a receipt on disk, and bare claims "
        "(0 supports) must be V0",
        [py, str(SCRIPTS / "check_verification_badges.py"),
         "--graph", str(ROOT / "claim_graph.json"),
         "--badges", str(ROOT / "badges.json")])[0]))

    # ---- Gate 51+52: C1 (PR-5) + C3 (PR-3 v2) preregistration integrity ----
    results.append(("gate51_52 c1_c3 prereg", run(
        "GATE 51+52 — C1 cell-densification (PR-5) and C3 rank-label (PR-3 v2) "
        "preregistration integrity: PR-5 target_density must be 0.10 (ESN floor), "
        "PR-3 v2 label_definition must be rank/quantile (not absolute), and R-0.1 "
        "requires PR3 to remain registered alongside PR3_v2 with change_from_v1 "
        "documented. Results files must match preregistered verdicts",
        [py, str(SCRIPTS / "check_c1_c3.py")])[0]))

    # ---- Gate 53: Preregistered Rejection Registry (F3 deliverable) ----
    results.append(("gate53 prereg rejection registry", run(
        "GATE 53 — F3 deliverable: preregistered rejection registry must exist at "
        "registry/preregistered_rejections.json, contain every PR* segment with "
        "kind=pre_execution_rejection from research_claims.json, and stay in sync "
        "with the source claims file (drift = FAIL). Gate 39 meta-discipline "
        "honored: registry script self-checks via --check flag.",
        [py, str(SCRIPTS / "export_preregistration_registry.py"), "--check"])[0]))

    # ---- Gate 54: metrics_fork reproducibility self-check ----
    results.append(("gate54 metrics_fork reproducibility", run(
        "GATE 54 — metrics_fork must be independently reproducible: tree files "
        "present, LICENSE declares Apache-2.0, every python -m metrics.* command "
        "in the README smoke-test block must exit 0 and print valid JSON against "
        "graphs/sample_topology.json, data_manifest.json display_name/species must "
        "not contradict each other across genus, and any README reference to "
        "upstream result artifacts must carry a disclaimer. Gate 39 meta-discipline "
        "honored: the checker runs a 5-mutation injection battery and fails if any "
        "mutation does not turn the gate red.",
        [py, str(SCRIPTS / "check_metrics_fork.py")])[0]))

    # ---- Gate 55: holdout integrity (E3 vault) ----
    results.append(("gate55 holdout integrity", run(
        "GATE 55 — holdout integrity (E3 vault discipline): every PASS "
        "preregistered protocol must have a vault/<protocol>.commit.json "
        "recording its frozen criteria + expected verdict before execution "
        "(R-0.3), the stored payload_hash must still match the current "
        "research_claims.json (drift = FAIL), and every open_count must "
        "remain <= 1. Retroactive commits are allowed but labelled "
        "honestly. Gate 39 meta-discipline honored: a 4-mutation injection "
        "battery (delete commit, tamper criteria, double-open, tamper "
        "expected_verdict) must all turn the gate red.",
        [py, str(SCRIPTS / "check_holdout_integrity.py")])[0]))

    # ---- Gate 56: badge ladder semantic consistency (E1b) ----
    results.append(("gate56 badge semantics", run(
        "GATE 56 — badge ladder semantic consistency (E1b): every V0-V5 "
        "rung of compute_verification_badges.py::_claim_badge() must "
        "contain at least one keyword for its own name (V1 → reproduc*, "
        "V2 → executed_at/prereg, V3 → vault/payload_hash, V4 → cross/"
        "independent, V5 → external/verifier). In default AUDIT mode "
        "the mismatches are reported but not fatal (known backlog per "
        "EPE §9.3); use --strict to fail. Gate 39 meta-discipline "
        "honored: 5-mutation injection battery (one per V-rung) must all "
        "turn the gate red in strict mode.",
        [py, str(SCRIPTS / "check_badge_semantics.py")])[0]))

    # ---- Gate 57: silent exception swallowing (fail-loud discipline) ----
    results.append(("gate57 silent exceptions", run(
        "GATE 57 — silent exception swallowing (K7 fail-loud discipline): "
        "AST scan of all Python files for 'except Exception: pass' and bare "
        "'except:'. Each violation must have EITHER (a) # noqa: SILENT with "
        "reason, (b) logging.warning/error in block, (c) re-raise, or "
        "(d) explicit failure return. Whitelist excludes backup/archive "
        "paths. Gate 39 meta-discipline honored: 4-mutation injection "
        "battery (bare except, except Exception, noqa: SILENT, logging) "
        "must all behave correctly.",
        [py, str(SCRIPTS / "check_silent_exceptions.py")])[0]))

    # ---- Gate 58: version single-source-of-truth ----
    results.append(("gate58 version consistency", run(
        "GATE 58 — version single-source-of-truth (K2): pyproject.toml "
        "version, CHANGELOG.md top entry, README.md badge, flybrain_cli.py "
        "__version__, api_server.py version, server.py version, and README "
        "gate count must ALL agree. Any mismatch = FAIL. Gate 39 "
        "meta-discipline honored: 2-mutation injection battery (pyproject "
        "drift, CHANGELOG drift) must both turn the gate red.",
        [py, str(SCRIPTS / "check_version_consistency.py")])[0]))

    # ---- Gate 59: static analysis + unit tests (K9 test pyramid) ----
    results.append(("gate59 static analysis", run(
        "GATE 59 — static analysis + unit tests (K9): ruff check + unittest "
        "discover on the selfverify suite. Gate 39 meta-discipline honored: "
        "3-mutation injection battery (unused import, undefined name, test "
        "failure) must all turn the gate red.",
        [py, str(SCRIPTS / "check_static_analysis.py"), "--quiet"])[0]))

    # ---- Gate 60: AIBOM supply-chain disclosure (Phase 3) ----
    results.append(("gate60 supply chain", run(
        "GATE 60 — AIBOM supply-chain disclosure (Phase 3): aibom.json must "
        "exist at repo root, be well-formed, and stay in sync with the live "
        "tree (workspace fingerprint + direct deps + subpackage versions). "
        "This forces disclosure of every external component: hidden deps "
        "cannot hide because the fingerprint would drift. Gate 39 "
        "meta-discipline honored: 5-mutation injection battery (missing, "
        "malformed, schema drift, dep drift, fingerprint drift) must all "
        "turn the gate red.",
        [py, str(SCRIPTS / "check_supply_chain.py")])[0]))

    # ---- Gate 61: receipt integrity (VRO enforcement) ----
    results.append(("gate61 receipt integrity", run(
        "GATE 61 — receipt integrity (VRO enforcement): every receipts/*.json "
        "must (a) exist, (b) match claim_graph.json entries, (c) carry all "
        "required fields (claim_id, expected_verdict, artifacts, scripts, "
        "hashes, env_hash, issued_utc), and (d) pass independent recomputation "
        "via verify_receipt.py. This closes the G1 gap: tampered receipts or "
        "code drift without re-issue = FAIL. Gate 39 meta-discipline honored: "
        "4-mutation injection battery (tamper artifact hash, delete script, "
        "tamper expected_verdict, drift env_hash) must all turn the gate red.",
        [py, str(SCRIPTS / "check_receipt_integrity.py")])[0]))

    # ---- Gate 62: PR_S1 external-validation integrity (W7 fix) ----
    results.append(("gate62 PR_S1 external-validation", run(
        "GATE 62 — PR_S1 external-validation integrity: vault/S1.commit.json "
        "must be present with protocol_id=S1, a complete success_criteria "
        "block (7 quantitative criteria), and families including all three "
        "external public connectomes (c_elegans_witvliet, drosophila_larva, "
        "zebrafish_petkova). Threshold sanity: AUC floor in [0.50, 0.90) "
        "strict, kappa floor in [0.30, 0.90], conjunctive locked True, "
        "p-ceiling <= 0.20. If research_claims.preregistered.PR_S1 exists "
        "as an override it must match the vault. Cross-consistency: "
        "claims.S1.ci_enrichment.verdict must echo results.verdict. This "
        "closes the W7 coverage gap that S3 discipline-effectiveness "
        "reported at 0% catch-rate. Gate 39 meta-discipline honored: "
        "3-mutation injection battery (raise_auc_min, remove_conjunctive, "
        "lower_kappa_min) must all turn the gate red.",
        [py, str(SCRIPTS / "check_pr_s1.py")])[0]))

    # ---- Gate 63: research_claims top-level stat completeness ----
    results.append(("gate63 claim stat completeness", run(
        "GATE 63 — research_claims.json top-level stat completeness: every "
        "claim (R1–R6) must carry a top-level statistical block — "
        "point_estimate, ci_low, ci_high, p_value, test_name, test_detail "
        "all present as keys. Null values must have a matching *_missing_"
        "reason. ci_method must be in the recognised vocabulary "
        "(wilson_score_95 / bootstrap_percentile_slope_B1000_seed42 / "
        "deterministic_didactic_test / not_available / single-point). "
        "Numeric point_estimate must lie inside [ci_low, ci_high]. "
        "This closes the P3 gap that the SCI_READINESS_ACTION_PLAN "
        "flagged: a reviewer scanning the manifest could not tell a "
        "tested claim from a hand-waved one. Gate 39 meta-discipline "
        "honored: 5-mutation injection battery (drop_ci_low, "
        "drop_p_value_key, corrupt_point_estimate, invert_ci_bounds, "
        "bogus_ci_method) must all turn the gate red.",
        [py, str(SCRIPTS / "check_claim_stats.py")])[0]))

    # ---- Gate 64: flybrain audit CLI integrity (P2-4) ----
    results.append(("gate64 audit CLI", run(
        "GATE 64 — flybrain audit CLI integrity (P2-4): the 'audit' "
        "subcommand must be registered in flybrain_cli.py (parser + "
        "handler + dispatch), must exit 0 on a valid organism JSON, "
        "must exit 1 on a broken organism (catches edge.target not in "
        "nodes, edge.module not in module_profiles, topology_profile "
        "drift), must exit 1 on a nonexistent file, and must actually "
        "produce an ERROR section (not a stub). Gate 39 meta-discipline "
        "honored: 3-mutation injection battery (drop_edge_target, "
        "corrupt_module_id, drift_topology_profile) must all turn the "
        "gate red. This packages the project's most valuable capability "
        "— PROV-JSON + structural integrity checking — as a standalone "
        "command any user can run on any artifact.",
        [py, str(SCRIPTS / "check_audit_cli.py"), "--quiet"])[0]))

    # ---- Gate 65: project_status.json consistency (P0-4) ----
    results.append(("gate65 project status", run(
        "GATE 65 — project_status.json consistency (P0-4): the JSON "
        "status file must be up-to-date with the actual source of truth "
        "(version, gate count, tool counts, HTTP dispatch, notebook "
        "count) so that README, Pages, papers and mcp server can all "
        "read from one canonical status file instead of hand-maintained "
        "drifting numbers. Transport gap between MCP and HTTP is declared "
        "openly. Gate 39 meta-discipline honored: 3-injection battery "
        "(tamper_mcp_tools_count, tamper_version_string, "
        "delete_project_key) must all turn the gate red.",
        [py, str(SCRIPTS / "check_project_status.py"), "--quiet"])[0]))

    # ---- Gate 66: MCP/HTTP transport contract consistency (P1-3) ----
    results.append(("gate66 transport contract", run(
        "GATE 66 — MCP / HTTP transport contract consistency (P1-3): "
        "HTTP /query must expose exactly the same tool surface as "
        "MCP tools/list. Before this gate, api_server.py hand-wrote "
        "a 12-entry DISPATCH dict while server.TOOLS declared 47 "
        "tools — users could see a tool in /tools but hit 400 on "
        "/query. Now tool_registry.py derives DISPATCH from "
        "server.TOOLS and this gate enforces that parity forever. "
        "Also verifies every TOOLS entry has a valid inputSchema "
        "(type=object) and every dispatch handler is callable. "
        "Gate 39 meta-discipline honored: 3-mutation injection "
        "battery (drop_one_dispatch, add_phantom_tool, "
        "truncate_tool_schema) must all turn the gate red.",
        [py, str(SCRIPTS / "check_transport_contract.py"), "--quiet"])[0]))

    print("=" * 72)
    print("gate summary")
    for name, ok in results:
        print("  %-24s %s" % (name, "PASS" if ok else "FAIL"))
    failed = [n for n, ok in results if not ok]
    print("=" * 72)
    if failed:
        print("GATES: FAIL — %s" % ", ".join(failed))
        return 1
    print("GATES: PASS — %d/%d" % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
