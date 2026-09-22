"""
Gate 7: Module architecture CONTRACT integrity.

This gate validates the *contract*, not the proprietary content. It passes on a
bare public install (Tier-2 absent) and on a full install (flybrain_core
present):

  1. Tier-2 artifact manifest is declared and the stub leaks no Tier-2 payload.
  2. Combinator middleware interface contract holds: every public function is
     callable and either returns real data (core present) or a well-formed
     tier2_required envelope (core absent). It never raises.
  3. Fingerprint is deterministic, change-sensitive, prefix-stable (Tier-1
     utility, ships in the open tier).
  4. HMAC fingerprint signing: keyed fingerprints are stable, differ from the
     unsigned SHA-256 fallback, and tamper verification rejects a modified
     organism.
  5. LICENSE-CLAUSE.md states the 3-tier split and the fingerprint format.
  6. The 4 combinator MCP tools are registered with handlers.
  7. Tier-1 boundary intact: tier-1 modules still import and tier-1 data files
     are not gitignored.

Content-level assertions about the discovered module libraries, the worm data
and the rule tables live in the private repo (they are Tier-2).

Exit code 0 on pass, 1 on fail.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "flybrain-connectome-mcp"
SCRIPTS = ROOT / "scripts"
NL = chr(10)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, ("- " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def main() -> int:
    print("=" * 72)
    print("GATE 7 - Module architecture CONTRACT integrity")
    print("=" * 72)

    sys.path.insert(0, str(MCP))
    import core_bridge as cb  # type: ignore

    # 1. Tier-2 manifest declared; stub is clean
    print(NL + "-- 1. Tier-2 manifest and clean stub --")
    check("TIER2_ARTIFACTS declared", len(cb.TIER2_ARTIFACTS) >= 10,
          str(len(cb.TIER2_ARTIFACTS)))
    seen, dup = set(), []
    for rel, _stubbed in cb.TIER2_ARTIFACTS:
        if rel in seen:
            dup.append(rel)
        seen.add(rel)
    check("manifest paths are unique", not dup, str(dup))
    stubbed = [r for r, s in cb.TIER2_ARTIFACTS if s]
    check("exactly one stubbed path", len(stubbed) == 1, str(stubbed))
    if stubbed:
        p = ROOT / stubbed[0]
        check("stub file exists", p.exists(), str(p))
        if p.exists():
            text = p.read_text(encoding="utf-8")
            leaked = [m for m in cb.TIER2_LEAK_MARKERS if m in text]
            check("stub leaks no Tier-2 payload", not leaked, str(leaked))
            check("stub is a thin seam (under 15 KB)", len(text) < 15000,
                  str(len(text)) + " B")

    # 2. Combinator interface contract
    print(NL + "-- 2. Combinator middleware interface contract --")
    try:
        import module_combinator as mc
        check("SCHEMA_VERSION exposed", mc.SCHEMA_VERSION == "1.1", str(mc.SCHEMA_VERSION))
        fns = ["list_rules", "validate_combination", "validate_nesting",
               "expand_organism", "get_multiplier_metrics",
               "audit_rules_against_data", "suggest_combinations",
               "cross_species_consistency", "find_rule", "find_all_rules"]
        missing = [f for f in fns if not callable(getattr(mc, f, None))]
        check("all public functions present", not missing, str(missing))
        env = mc.list_rules()
        gated = isinstance(env, dict) and env.get("status") == "tier2_required"
        live = isinstance(env, dict) and not gated
        check("list_rules() returns data or a tier2_required envelope",
              gated or live, "gated" if gated else "live")
        if gated:
            check("envelope names the tool",
                  env.get("tool") == "list_combination_rules", str(env.get("tool")))
            check("envelope carries an actionable message",
                  isinstance(env.get("message"), str) and len(env.get("message")) > 40)
            check("envelope carries no rule payload",
                  "rules" not in env and "COMBINATION_RULES" not in env)
        else:
            check("live combinator returns rules", "rules" in env, str(list(env.keys())))
            check("live combinator rules >= 12", len(env.get("rules", [])) >= 12,
                  str(len(env.get("rules", []))))
        m = mc.get_multiplier_metrics()
        if isinstance(m, dict) and m.get("status") == "tier2_required":
            check("get_multiplier_metrics() degrades gracefully", True)
        else:
            check("get_multiplier_metrics() returns semantics",
                  m.get("semantics") is not None)
            perf = m["semantics"].get("performance", {})
            check("performance multiplier honestly unverified",
                  perf.get("measured") is False)
    except Exception as e:
        check("middleware imports and is callable", False, str(e))

    # 3. Fingerprint determinism (Tier-1 utility)
    print(NL + "-- 3. Fingerprint determinism and change-sensitivity --")
    try:
        sys.path.insert(0, str(SCRIPTS))
        from fingerprint_organism import compute_fingerprint
        org1 = {"name": "test", "modules": [{"name": "sensory", "count": 2}], "seed": 42}
        fp1, fp2 = compute_fingerprint(org1), compute_fingerprint(org1)
        check("fingerprint deterministic", fp1 == fp2, fp1[:40])
        org3 = json.loads(json.dumps(org1))
        org3["modules"][0]["count"] = 999
        check("fingerprint sensitive to change", fp1 != compute_fingerprint(org3))
        check("prefix stable", fp1.startswith("flybrain:organism-v1:"), fp1[:26])
    except Exception as e:
        check("fingerprint computes", False, str(e))

    # 4. HMAC signing (unforgeable without the server key)
    print(NL + "-- 4. HMAC fingerprint signing --")
    try:
        from fingerprint_organism import compute_fingerprint, sign_organism, verify_signature
        org1 = {"name": "test", "modules": [{"name": "sensory", "count": 2}], "seed": 42}
        unsigned = compute_fingerprint(org1)
        signed = compute_fingerprint(org1, key="server-secret")
        check("HMAC stable with same key",
              signed == compute_fingerprint(org1, key="server-secret"))
        check("HMAC differs from unsigned (key matters)", signed != unsigned)
        check("unsigned stable (backward compat)", unsigned == compute_fingerprint(org1))
        s = sign_organism(org1)
        check("sign_organism returns a fingerprint",
              s["fingerprint"].startswith("flybrain:organism-v1:"))
        check("sign_organism honest about key absence",
              s["key_present"] is False and s["signed"] is False)
        tampered = json.loads(json.dumps(org1))
        tampered["seed"] = 99
        check("verify_signature rejects tampered organism",
              verify_signature(tampered, signed)["valid"] is False)
        check("verify_signature accepts authentic organism",
              verify_signature(org1, signed, key="server-secret")["valid"] is True)
    except Exception as e:
        check("HMAC scheme computes", False, str(e))

    # 5. LICENSE-CLAUSE.md
    print(NL + "-- 5. Anti-plagiarism documentation --")
    lic = ROOT / "LICENSE-CLAUSE.md"
    check("LICENSE-CLAUSE.md exists", lic.exists())
    if lic.exists():
        text = lic.read_text(encoding="utf-8")
        check("mentions Tier 1 (MIT)", "MIT" in text and "Tier 1" in text)
        check("mentions Tier 2 (Proprietary)", "Proprietary" in text and "Tier 2" in text)
        check("mentions Tier 3 (Service-side)", "Service" in text and "Tier 3" in text)
        check("mentions fingerprint format", "flybrain:organism-v1" in text)

    # 6. MCP tools registered
    print(NL + "-- 6. MCP tools registered (offline) --")
    server_text = (MCP / "mcp_connectome" / "server.py").read_text(encoding="utf-8")
    for tool_name in ("list_combination_rules", "validate_combination",
                      "expand_organism", "get_multiplier_metrics"):
        check("tool '%s' in TOOLS list" % tool_name, '"%s"' % tool_name in server_text)
        check("handler for '%s' exists" % tool_name,
              'name == "%s"' % tool_name in server_text)

    # 7. Tier-1 boundary intact
    print(NL + "-- 7. Tier-1 boundary intact --")
    try:
        import module_registry
        check("module_registry imports", True)
    except Exception as e:
        check("module_registry imports", False, str(e))
    for rel in ("male_cns/neuropil_stats.json",
                "male_cns/virtual_organisms/preset_minimal_reflex.json"):
        check("tier-1 data present: %s" % rel, (ROOT / rel).exists())
    import subprocess
    for rel in ("male_cns/neuropil_stats.json",
                "male_cns/virtual_organisms/preset_minimal_reflex.json",
                "flybrain-connectome-mcp/module_registry.py",
                "flybrain-connectome-mcp/core_bridge.py"):
        try:
            r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel],
                               capture_output=True)
            check("not gitignored: %s" % rel, r.returncode != 0,
                  "git check-ignore rc=%d" % r.returncode)
        except FileNotFoundError:
            check("git available for check-ignore", False, "git not on PATH")

    print(NL + "=" * 72)
    if failures:
        print("GATE 7: FAIL - %d checks failed: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("GATE 7: PASS - architecture contract holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
