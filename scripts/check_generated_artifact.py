#!/usr/bin/env python3
"""Assert that a generated organism is *real*, not merely produced.

`generate` exiting 0 proves nothing about the artifact — a generator that
writes an empty skeleton would also exit 0. This checker reads the emitted
JSON and verifies structural invariants that the generator is supposed to
guarantee, so CI fails on silent regressions instead of on crashes only.

Checked on `<name>.json` (the organism):
  * schema_version present
  * metrics.n_nodes / metrics.n_edges > 0, and consistent with the
    actual lengths of organism.nodes / organism.edges
  * motif_provenance records the snapshot it came from (mode + sha256)

Checked on `swarmlabs/<name>.swarm.json` (the downstream config):
  * swarm.agents / swarm.edges non-empty
  * validation.dangling_edges == 0
  * validation.leader_is_module_member is False  (leader must sit outside
    every module — the invariant a frozen phase-3 artifact once violated)
  * validation.weights_in_range is True
  * prov_json carries a W3C PROV chain (wasAssociatedWith + FlyCellAtlas)

Usage:
    python scripts/check_generated_artifact.py --dir tmp/ci_out --name ci_smoke
    python scripts/check_generated_artifact.py --dir out   # any *.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


class Failure(Exception):
    pass


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise Failure("%s is not valid JSON: %s" % (path, e)) from e


def _pick(root: Path, name: str | None, pattern: str) -> Path | None:
    """Prefer an exact `<name>.json`, else any match of the glob."""
    if name:
        exact = sorted(root.rglob("%s%s" % (name, pattern)))
        if exact:
            return exact[0]
    hits = sorted(root.rglob("*" + pattern))
    return hits[0] if hits else None


def check(root: Path, name: str | None) -> list[str]:
    log: list[str] = []

    if not root.exists():
        raise Failure("output directory does not exist: %s" % root)

    organism_path = _pick(root, name, ".json")
    # `.swarm.json` also ends in `.json`; exclude it from the organism pick.
    if organism_path and organism_path.name.endswith(".swarm.json"):
        others = [p for p in sorted(root.rglob("*.json"))
                  if not p.name.endswith(".swarm.json")]
        organism_path = others[0] if others else None
    if not organism_path:
        raise Failure("no organism JSON found under %s" % root)
    log.append("organism artifact: %s" % organism_path)

    org = _load(organism_path)
    if not org.get("schema_version"):
        raise Failure("organism has no schema_version")
    log.append("  schema_version=%s kind=%s" % (org["schema_version"], org.get("kind")))

    metrics = org.get("metrics") or {}
    for key in ("n_nodes", "n_edges"):
        val = metrics.get(key)
        if not isinstance(val, int) or val <= 0:
            raise Failure("metrics.%s is not a positive int: %r" % (key, val))
    body = org.get("organism") or {}
    nodes, edges = body.get("nodes") or [], body.get("edges") or []
    if not nodes or not edges:
        raise Failure("organism.nodes/organism.edges are empty")
    # The metric must describe the payload; a mismatch means one of them lied.
    if metrics["n_nodes"] != len(nodes):
        raise Failure("metrics.n_nodes=%d but organism.nodes has %d"
                      % (metrics["n_nodes"], len(nodes)))
    if metrics["n_edges"] != len(edges):
        raise Failure("metrics.n_edges=%d but organism.edges has %d"
                      % (metrics["n_edges"], len(edges)))
    log.append("  nodes=%d edges=%d (metrics agree with payload)"
               % (len(nodes), len(edges)))

    prov = org.get("motif_provenance") or {}
    if not prov.get("mode"):
        raise Failure("motif_provenance.mode missing — artifact is not traceable")
    if not (prov.get("doc_sha256") or prov.get("snapshot_sha256")):
        raise Failure("motif_provenance carries no snapshot hash — cannot trace back")
    log.append("  provenance mode=%s sha256=%s"
               % (prov["mode"], str(prov.get("doc_sha256")
                                    or prov.get("snapshot_sha256"))[:12]))

    swarm_path = _pick(root, name, ".swarm.json")
    if not swarm_path:
        raise Failure("no *.swarm.json emitted — downstream config missing")
    log.append("swarm config: %s" % swarm_path)

    sw = _load(swarm_path)
    if not sw.get("schema_version"):
        raise Failure("swarm config has no schema_version")
    swarm = sw.get("swarm") or {}
    agents, sw_edges = swarm.get("agents") or [], swarm.get("edges") or []
    if not agents:
        raise Failure("swarm.agents is empty")
    if not sw_edges:
        raise Failure("swarm.edges is empty")
    log.append("  agents=%d edges=%d schema_version=%s"
               % (len(agents), len(sw_edges), sw["schema_version"]))

    val = swarm.get("validation") or {}
    if val.get("dangling_edges") not in (0, None):
        raise Failure("validation.dangling_edges=%r (expected 0)"
                      % val.get("dangling_edges"))
    if val.get("leader_is_module_member") is not False:
        raise Failure("validation.leader_is_module_member=%r — the coordinator "
                      "must not belong to a module"
                      % val.get("leader_is_module_member"))
    if val.get("weights_in_range") is not True:
        raise Failure("validation.weights_in_range=%r (expected True)"
                      % val.get("weights_in_range"))
    log.append("  invariants: dangling_edges=%s leader_is_module_member=%s "
               "weights_in_range=%s"
               % (val.get("dangling_edges"), val.get("leader_is_module_member"),
                  val.get("weights_in_range")))

    prov_span = json.dumps(sw.get("prov_json") or {}, ensure_ascii=False)
    if not prov_span or prov_span == "{}":
        raise Failure(
            "swarm config carries no prov_json bundle. The W3C PROV-JSON "
            "serializer is the optional 'dataprov' package — install it with "
            "`pip install dataprov` (or `pip install \"flybrain-connectome[prov]\"`) "
            "if this environment is supposed to emit provenance.")
    for token in ("wasAssociatedWith", "FlyCellAtlas"):
        if token not in prov_span:
            raise Failure("prov_json lost %r — the provenance chain is broken" % token)
    log.append("  prov_json=%d bytes, chain intact (wasAssociatedWith + FlyCellAtlas)"
               % len(prov_span))

    return log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, type=Path,
                    help="directory the generator wrote into")
    ap.add_argument("--name", default=None,
                    help="organism name used with --out (recommended)")
    args = ap.parse_args()

    print("artifact gate — %s" % args.dir)
    try:
        for line in check(args.dir, args.name):
            print(line)
    except Failure as e:
        print()
        print("ARTIFACT GATE: FAIL — %s" % e)
        return 1
    print()
    print("ARTIFACT GATE: PASS")
    return 0


def _make_valid_artifact(td: Path) -> tuple[Path, Path]:
    """Create a minimal valid organism + swarm config pair in td."""
    org = td / "test_org.json"
    org.write_text(json.dumps({
        "schema_version": "1.0.0",
        "kind": "organism",
        "metrics": {"n_nodes": 3, "n_edges": 2},
        "organism": {
            "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
            "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}]
        },
        "motif_provenance": {
            "mode": "snapshot",
            "doc_sha256": "abc123def456"
        }
    }), encoding="utf-8")

    sw = td / "swarmlabs" / "test_org.swarm.json"
    sw.parent.mkdir(parents=True, exist_ok=True)
    sw.write_text(json.dumps({
        "schema_version": "1.0.0",
        "swarm": {
            "agents": [{"id": "a1"}, {"id": "a2"}],
            "edges": [{"from": "a1", "to": "a2"}],
            "validation": {
                "dangling_edges": 0,
                "leader_is_module_member": False,
                "weights_in_range": True
            }
        },
        "prov_json": {
            "wasAssociatedWith": "FlyCellAtlas",
            "FlyCellAtlas": "https://example.com"
        }
    }), encoding="utf-8")

    return org, sw


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: inject defects into generated artifacts
    and assert the gate goes red. Each injection exercises one of the
    failure classes the gate declares.

    Apply and restore are structurally separate (tempfile + JSON mutate),
    so no injection leaks state into the next one.
    """
    bad = 0
    n_inj = 0

    def expect(name, mutate_fn):
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate_artifact_inj_"))
        try:
            _make_valid_artifact(td)
            # Find the JSON files and mutate them
            for jf in td.rglob("*.json"):
                doc = json.loads(jf.read_text(encoding="utf-8"))
                mutate_fn(jf, doc)
                jf.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

            # Run the checker via main() with --dir and --name
            old_argv = sys.argv[:]
            sys.argv = ["check_generated_artifact.py", "--dir", str(td), "--name", "test_org"]
            try:
                rc = main()
            finally:
                sys.argv = old_argv
        finally:
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. Organism has no schema_version.
    def _inj_no_schema(jf, doc):
        if jf.name.endswith(".swarm.json"):
            return
        doc.pop("schema_version", None)

    expect("organism has no schema_version", _inj_no_schema)

    # 2. metrics.n_nodes disagrees with actual node count.
    def _inj_bad_n_nodes(jf, doc):
        if jf.name.endswith(".swarm.json"):
            return
        doc["metrics"]["n_nodes"] = 99

    expect("metrics.n_nodes disagrees with actual node count", _inj_bad_n_nodes)

    # 3. motif_provenance.mode is missing.
    def _inj_no_prov_mode(jf, doc):
        if jf.name.endswith(".swarm.json"):
            return
        doc["motif_provenance"].pop("mode", None)

    expect("motif_provenance.mode is missing", _inj_no_prov_mode)

    # 4. validation.dangling_edges is non-zero.
    def _inj_bad_dangling(jf, doc):
        if not jf.name.endswith(".swarm.json"):
            return
        doc["swarm"]["validation"]["dangling_edges"] = 5

    expect("validation.dangling_edges is non-zero", _inj_bad_dangling)

    # 5. validation.leader_is_module_member is True (invariant violation).
    def _inj_bad_leader(jf, doc):
        if not jf.name.endswith(".swarm.json"):
            return
        doc["swarm"]["validation"]["leader_is_module_member"] = True

    expect("validation.leader_is_module_member is True (invariant violation)",
           _inj_bad_leader)

    # 6. prov_json is missing the wasAssociatedWith token.
    def _inj_bad_prov_json(jf, doc):
        if not jf.name.endswith(".swarm.json"):
            return
        doc["prov_json"] = {"FlyCellAtlas": "https://example.com"}

    expect("prov_json lost wasAssociatedWith token", _inj_bad_prov_json)

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"ARTIFACT GATE: FAIL -- {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    sys.exit(_run_with_injections())
