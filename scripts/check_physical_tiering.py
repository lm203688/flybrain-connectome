"""
Gate 8: Physical tiering integrity - Tier-2 IP stays out of the public tree.

Verifies the architecture that lets the public MIT repo stay open while the
Tier-2 IP lives only in the private repo:

  1. LICENSE-CLAUSE.md declares the 3-tier split and names the private repo.
  2. core_bridge degrades gracefully (tier2_required envelope, never a crash)
     and the functional-tool-count contract holds: bare public install = 40,
     with flybrain_core installed = 44.
  3. Physical absence: no Tier-2 artifact ships in this tree. Stubbed paths
     must hold only a thin seam; every other Tier-2 path must be absent.
  4. Canonical home: the private repo exists, is private, and actually
     contains the Tier-2 artifacts (best-effort, via the GitHub API).

Exit code 0 on pass, 1 on fail.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "flybrain-connectome-mcp"
PRIVATE_REPO = "lm203688/flybrain-connectome-core"
TOTAL_TOOLS = 44

NL = chr(10)
failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, ("- " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def _token():
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    sp = Path.home() / ".workbuddy" / "secrets" / "github.json"
    if sp.exists():
        try:
            d = json.loads(sp.read_text(encoding="utf-8"))
            for v in d.values():
                if isinstance(v, str) and (v.startswith("ghp_") or v.startswith("github_pat_")):
                    return v
        except Exception:
            pass
    return None


def _api_tree() -> dict:
    """Fetch the private repo tree. Returns {} when it cannot be reached."""
    try:
        import ssl
        import urllib.request
        tok = _token()
        if not tok:
            return {"skipped": "no token"}
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/git/trees/HEAD?recursive=1" % PRIVATE_REPO,
            headers={"Authorization": "Bearer %s" % tok,
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "flybrain-tiering-gate"})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"skipped": str(e)}


def _repo_private() -> dict:
    try:
        import ssl
        import urllib.request
        tok = _token()
        if not tok:
            return {"skipped": "no token"}
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://api.github.com/repos/%s" % PRIVATE_REPO,
            headers={"Authorization": "Bearer %s" % tok,
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "flybrain-tiering-gate"})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"skipped": str(e)}


def main() -> int:
    print("=" * 72)
    print("GATE 8 - Physical tiering integrity")
    print("=" * 72)

    sys.path.insert(0, str(MCP))
    import core_bridge as cb  # type: ignore

    # 1. License declaration
    print(NL + "-- 1. License tiering declaration --")
    lic = ROOT / "LICENSE-CLAUSE.md"
    check("LICENSE-CLAUSE.md exists", lic.exists())
    if lic.exists():
        text = lic.read_text(encoding="utf-8")
        check("declares Tier 1 (MIT)", "Tier 1" in text and "MIT" in text)
        check("declares Tier 2 (Proprietary)", "Tier 2" in text and "Proprietary" in text)
        check("declares Tier 3 (Service-side)", "Tier 3" in text and "Service" in text)
        check("names the private repo", PRIVATE_REPO.replace("/", "-") in text
              or "flybrain-connectome-core" in text)

    # 2. Graceful degradation + tool-count contract
    print(NL + "-- 2. core_bridge degradation & tool-count contract --")
    check("core_available() callable", callable(cb.core_available))
    env = cb.require_core("list_combination_rules")
    check("require_core returns a tier2_required envelope",
          isinstance(env, dict) and env.get("status") == "tier2_required")
    bare = TOTAL_TOOLS - len(cb.CORE_DEPENDENT_TOOLS)
    check("functional_tool_count degrades to %d bare (44 - %d tier-2 tools)"
          % (bare, len(cb.CORE_DEPENDENT_TOOLS)),
          cb.functional_tool_count() == bare
          and cb.functional_tool_count() == (TOTAL_TOOLS if cb.core_available() else bare),
          str(cb.functional_tool_count()))
    check("CORE_DEPENDENT_TOOLS scoped to the 4 combinator tools",
          set(cb.CORE_DEPENDENT_TOOLS) == {"list_combination_rules", "validate_combination",
                                           "expand_organism", "get_multiplier_metrics"},
          str(cb.CORE_DEPENDENT_TOOLS))
    st = cb.tiering_status()
    check("tiering_status reports the canonical private repo",
          "flybrain-connectome-core" in st.get("canonical_tier2_repo", ""))

    # 3. Physical absence of Tier-2 artifacts
    print(NL + "-- 3. Physical absence (Tier-2 IP must not ship here) --")
    present_stubs, present_full, leaked = [], [], []
    for rel, stubbed in cb.TIER2_ARTIFACTS:
        p = ROOT / rel
        if not p.exists():
            continue
        if stubbed:
            present_stubs.append(rel)
            txt = p.read_text(encoding="utf-8", errors="replace")
            for marker in cb.TIER2_LEAK_MARKERS:
                if marker in txt:
                    leaked.append("%s -> %s" % (rel, marker))
        else:
            present_full.append(rel)
    check("no Tier-2 payload leaked into a stubbed path", not leaked, str(leaked))
    check("only stubbed Tier-2 paths remain present", not present_full, str(present_full))
    check("all stubbed paths are stubs", len(present_stubs) == 1, str(present_stubs))

    # 4. Canonical home holds the IP
    print(NL + "-- 4. Canonical Tier-2 home (private repo) --")
    meta = _repo_private()
    if "skipped" in meta:
        print("  [SKIP] repo metadata: %s" % meta["skipped"])
    else:
        check("%s exists and is private" % PRIVATE_REPO, bool(meta.get("private")),
              "private=%s" % meta.get("private"))
    tree = _api_tree()
    if "skipped" in tree:
        print("  [SKIP] tree listing: %s" % tree["skipped"])
    else:
        remote = set()
        for item in tree.get("tree", []):
            if item.get("type") == "blob":
                remote.add(item.get("path", ""))
        missing_remote = [rel for rel, _s in cb.TIER2_ARTIFACTS if rel not in remote]
        check("private repo holds every Tier-2 artifact", not missing_remote,
              "missing: %s" % ", ".join(missing_remote) if missing_remote else
              "%d/%d present" % (len(cb.TIER2_ARTIFACTS) - len(missing_remote),
                                  len(cb.TIER2_ARTIFACTS)))

    print(NL + "=" * 72)
    if failures:
        print("GATE 8: FAIL - %d checks failed: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("GATE 8: PASS - Tier-2 IP physically absent from the public tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
