"""
Gate 7: Module architecture integrity.

Verifies:
  1. Neuropil modules file exists and has valid structure (discovered_modules_neuropil.json)
  2. Worm data files exist and have valid structure (data/worm/worm_modules.json)
  3. Cross-species comparison table is present
  4. Combinator middleware loads and all rules parse
  5. Fingerprint is deterministic and change-sensitive

Exit code 0 on pass, 1 on fail.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MALE = ROOT / "male_cns"
WORM = ROOT / "data" / "worm"
MCP = ROOT / "flybrain-connectome-mcp"
SCRIPTS = ROOT / "scripts"

failures: list[str] = []

def check(name: str, cond: bool, detail: str = ""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, ("- " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def main() -> int:
    print("=" * 72)
    print("GATE 7 — Module architecture integrity")
    print("=" * 72)

    # 1. Neuropil modules
    print("\n-- 1. Neuropil module discovery (superclass → neuropil descent) --")
    neu_path = MALE / "discovered_modules_neuropil.json"
    check("neuropil file exists", neu_path.exists(), str(neu_path))
    if neu_path.exists():
        try:
            neu = json.loads(neu_path.read_text(encoding="utf-8"))
            check("schema_version present", "schema_version" in neu)
            check("≥1 units", len(neu.get("units", [])) >= 1)
            check("total_synapses > 0", neu.get("total_synapses", 0) > 0)
            check("n_units field matches", neu.get("n_units") == len(neu.get("units", [])))
            # Each unit has required fields
            unit_ok = all(
                all(k in u for k in ("unit_id", "synapses", "n_neuropils", "members"))
                for u in neu.get("units", [])
            )
            check("all units have required keys", unit_ok)
        except json.JSONDecodeError as e:
            check("JSON parses", False, str(e))

    # 2. Worm data
    print("\n-- 2. Cross-species (worm) data --")
    worm_path = WORM / "worm_modules.json"
    check("worm file exists", worm_path.exists(), str(worm_path))
    if worm_path.exists():
        try:
            worm = json.loads(worm_path.read_text(encoding="utf-8"))
            check("schema_version present", "schema_version" in worm)
            check("counts.neurons_total ~ 302", 250 <= worm.get("counts", {}).get("neurons_total", 0) <= 350)
            check("≥1 units", len(worm.get("units", [])) >= 1)
            check("cross_species_comparison present", "cross_species_comparison" in worm)
            xsc = worm.get("cross_species_comparison", {})
            check("conserved_modules listed", len(xsc.get("conserved_modules", [])) >= 1)
            check("fruit_fly_specific listed", len(xsc.get("fruit_fly_specific", [])) >= 1)
            check("worm_specific listed", len(xsc.get("worm_specific", [])) >= 1)
        except json.JSONDecodeError as e:
            check("JSON parses", False, str(e))

    # 3. Combinator middleware
    print("\n-- 3. Combinator middleware loads and rules parse --")
    try:
        sys.path.insert(0, str(MCP))
        import module_combinator as mc
        check("COMBINATION_RULES ≥ 1", len(mc.COMBINATION_RULES) >= 1)
        check("NESTING_RULES ≥ 1", len(mc.NESTING_RULES) >= 1)
        check("MULTIPLIER_SEMANTICS has ≥3 keys",
              len(mc.MULTIPLIER_SEMANTICS) >= 3
              and {"combinatorial", "structural", "performance"}.issubset(mc.MULTIPLIER_SEMANTICS.keys()))
        # Validate a real combo
        r = mc.validate_combination([
            {"from_category": "sensory_input", "to_category": "recurrent_memory",
             "from_superclass": "ol_sensory", "to_superclass": "ol_intrinsic"}
        ])
        check("validate_combination returns compatible for known-good pair",
              r.get("compatible") is True)
        # Multiplier metrics
        m = mc.get_multiplier_metrics()
        check("multiplier metrics returned", m.get("semantics") is not None)
        check("performance marked as unverified",
              m["semantics"]["performance"]["measured"] is False)
    except Exception as e:
        check("middleware imports", False, str(e))

    # 4. Fingerprint determinism
    print("\n-- 4. Fingerprint determinism & change-sensitivity --")
    try:
        sys.path.insert(0, str(SCRIPTS))
        from fingerprint_organism import compute_fingerprint
        org1 = {"name": "test", "modules": [{"name": "sensory", "count": 2}], "seed": 42}
        fp1 = compute_fingerprint(org1)
        fp2 = compute_fingerprint(org1)
        check("fingerprint deterministic (same input → same output)", fp1 == fp2, fp1[:40])
        org3 = json.loads(json.dumps(org1))
        org3["modules"][0]["count"] = 999
        fp3 = compute_fingerprint(org3)
        check("fingerprint sensitive to change", fp1 != fp3)
        # Test with real organism file
        real_files = list((MALE / "virtual_organisms").glob("organism_*.json"))
        if real_files:
            real = json.loads(real_files[0].read_text(encoding="utf-8"))
            real_fp = compute_fingerprint(real)
            check("real organism fingerprint starts with prefix", real_fp.startswith("flybrain:organism-v1:"))
    except Exception as e:
        check("fingerprint computes", False, str(e))

    # 5. LICENSE-CLAUSE.md present
    print("\n-- 5. Anti-plagiarism documentation --")
    lic_clause = ROOT / "LICENSE-CLAUSE.md"
    check("LICENSE-CLAUSE.md exists", lic_clause.exists())
    if lic_clause.exists():
        text = lic_clause.read_text(encoding="utf-8")
        check("mentions Tier 1 (MIT)", "MIT" in text and "Tier 1" in text)
        check("mentions Tier 2 (Proprietary)", "Proprietary" in text and "Tier 2" in text)
        check("mentions Tier 3 (Service-side)", "Service" in text and "Tier 3" in text)
        check("mentions fingerprint format", "flybrain:organism-v1" in text)

    # 6. New MCP tools registered (offline check)
    print("\n-- 6. MCP tools registered (offline) --")
    server_path = MCP / "mcp_connectome" / "server.py"
    server_text = server_path.read_text(encoding="utf-8")
    for tool_name in ("list_combination_rules", "validate_combination",
                      "expand_organism", "get_multiplier_metrics"):
        check(f"tool '{tool_name}' in TOOLS list", f'"{tool_name}"' in server_text)
        check(f"handler for '{tool_name}' exists", f'name == "{tool_name}"' in server_text)

    print("\n" + "=" * 72)
    if failures:
        print("GATE 7: FAIL — %d checks failed: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("GATE 7: PASS — all checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
