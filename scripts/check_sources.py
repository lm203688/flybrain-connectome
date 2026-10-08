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
import sys
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


if __name__ == "__main__":
    sys.exit(main())
