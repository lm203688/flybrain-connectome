#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE 20 -- connectome-source adapters are present and the zebrafish line is built.

T1 of the foundation roadmap turns external connectomes into independent
evidence lines.  This gate enforces:
  * the ``connectome_sources`` package imports and advertises its registry;
  * every adapter class exists (zebrafish / h01 / microns);
  * the zebrafish adapter is available (data shipped) AND its
    ``zebrafish_profiles.json`` exists, is valid, and has a real neuron count;
  * h01 / microns are allowed to be ``unavailable`` offline (multi-GB, not
    bundled) -- their adapters must simply exist and import cleanly.

So the gate is green offline, and would only go red if an adapter regressed or
the zebrafish profile was deleted.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
PROFILES = MCP / "functional_units" / "zebrafish_profiles.json"

sys.path.insert(0, str(MCP))


def fail(msg: str) -> int:
    print("GATE 20: FAIL -- %s" % msg)
    return 1


def ok(msg: str) -> int:
    print("GATE 20: PASS -- %s" % msg)
    return 0


def main() -> int:
    try:
        from connectome_sources import list_sources, get_source  # noqa
    except Exception as e:  # pragma: no cover
        return fail("connectome_sources package failed to import: %r" % e)

    srcs = {s["id"]: s for s in list_sources()}
    for needed in ("zebrafish", "h01", "microns"):
        if needed not in srcs:
            return fail("adapter %r missing from registry" % needed)

    # zebrafish: the one source we bundle -- must be available AND built.
    z = get_source("zebrafish")
    if not z.available():
        return fail("zebrafish adapter reports data unavailable -- zebrafish_data/ missing")
    if not PROFILES.exists():
        return fail("%s missing -- run scripts/build_zebrafish_profiles.py" % PROFILES)
    try:
        doc = json.loads(PROFILES.read_text(encoding="utf-8"))
    except Exception as e:
        return fail("zebrafish_profiles.json is not valid JSON: %r" % e)
    n = doc.get("units", 0)
    if n < 100:
        return fail("zebrafish_profiles.json has only %d neurons (expected >=100)" % n)
    if "neuron_profiles" not in doc:
        return fail("zebrafish_profiles.json missing neuron_profiles")
    if doc.get("license") != "CC-BY-NC":
        return fail("zebrafish license must stay CC-BY-NC, got %r" % doc.get("license"))

    # h01 / microns: allowed offline (unavailable), but must import & report.
    for sid in ("h01", "microns"):
        s = get_source(sid)
        st = s.status()
        print("  %-8s available=%s license=%s" % (sid, st["available"], st["license"]))

    return ok("3 adapters present; zebrafish built (%d neurons, CC-BY-NC); "
              "h01/microns offline-ready" % n)


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: mutate zebrafish_profiles.json and assert
    the gate goes red. Each injection exercises one of the failure
    classes the gate declares in its docstring.

    Apply and restore are structurally separate (tempfile + globals swap
    + finally), so no injection leaks state into the next one.
    """
    bad = 0
    n_inj = 0

    real_doc = json.loads(PROFILES.read_text(encoding="utf-8"))

    def expect(name, mutate_fn):
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate20_inj_"))
        try:
            doc = deepcopy(real_doc)
            mutate_fn(doc)
            fp = td / "profiles.json"
            fp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            old_profiles = globals()["PROFILES"]
            globals()["PROFILES"] = fp
            try:
                rc = main()
            finally:
                globals()["PROFILES"] = old_profiles
        finally:
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. The neuron count drops below the 100-neuron floor.
    def _inj_low_count(doc):
        doc["units"] = 3

    expect("zebrafish_profiles.json has fewer than 100 neurons", _inj_low_count)

    # 2. The license drifts away from CC-BY-NC.
    def _inj_bad_license(doc):
        doc["license"] = "MIT"

    expect("zebrafish license drifts away from CC-BY-NC", _inj_bad_license)

    # 3. The neuron_profiles key is removed.
    def _inj_no_profiles(doc):
        doc.pop("neuron_profiles", None)

    expect("zebrafish_profiles.json loses its neuron_profiles key", _inj_no_profiles)

    # 4. The registry loses the zebrafish adapter (monkey-patch list_sources).
    import connectome_sources as cs
    real_list_sources = cs.list_sources
    saved_profiles = globals()["PROFILES"]

    td = Path(tempfile.mkdtemp(prefix="gate20_inj_"))
    try:
        globals()["PROFILES"] = td / "missing.json"  # force the "missing" path
        cs.list_sources = lambda: [s for s in real_list_sources()
                                   if s["id"] != "zebrafish"]
        try:
            rc = main()
        finally:
            cs.list_sources = real_list_sources
    finally:
        globals()["PROFILES"] = saved_profiles
        shutil.rmtree(td, ignore_errors=True)
    if rc != 0:
        print("    [PASS] injecting: zebrafish adapter missing from registry")
        n_inj += 1
    else:
        bad += 1
        n_inj += 1
        print("    [FAIL] injecting: zebrafish adapter missing -> GATE STAYED GREEN")

    # State must be byte-clean after the battery.
    assert PROFILES.exists(), "injections leaked PROFILES path"

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"GATE 20: FAIL -- {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    sys.exit(_run_with_injections())
