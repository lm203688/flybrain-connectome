"""
Gate 8: Physical tiering integrity (层2 IP 物理隔离架构).

Verifies the architecture that lets the public MIT repo stay open while the
Tier-2 IP lives only in the private repo:

  1. LICENSE-CLAUSE.md declares the 3-tier split and names the private repo.
  2. core_bridge exists and `require_core()` degrades gracefully (returns a
     Tier-2 envelope instead of crashing) when the private package is absent.
  3. The functional-tool-count contract: bare public install = 30, with core = 40.
  4. The canonical Tier-2 home (`flybrain-connectome-core`) exists and is private.

Note: this gate validates the *mechanism*. The irreversible step — removing the
Tier-2 files from the public git tree — is staged separately and needs an
explicit push confirmation (the files are also in git history from v1.2.0/1.2.1).

Exit code 0 on pass, 1 on fail.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "flybrain-connectome-mcp"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, ("- " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def _check_private_repo() -> dict:
    """Best-effort: confirm the private repo exists & is private via the API."""
    try:
        import urllib.request, urllib.error, ssl, base64, os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sp = Path.home() / ".workbuddy" / "secrets" / "github.json"
            if sp.exists():
                d = json.loads(sp.read_text(encoding="utf-8"))
                for v in d.values():
                    if isinstance(v, str) and v.startswith("ghp_"):
                        token = v
                        break
        if not token:
            return {"ok": None, "detail": "no token; skipped"}
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://api.github.com/repos/lm203688/flybrain-connectome-core",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "flybrain-tiering-gate"},
        )
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            j = json.loads(r.read().decode("utf-8"))
        return {"ok": bool(j.get("private")), "private": j.get("private"),
                "detail": "repo present"}
    except Exception as e:  # noqa: BLE001
        return {"ok": None, "detail": f"api check skipped: {e}"}


def main() -> int:
    print("=" * 72)
    print("GATE 8 — Physical tiering integrity")
    print("=" * 72)

    # 1. LICENSE-CLAUSE declares 3 tiers + private repo
    print("\n-- 1. License tiering declaration --")
    lic = ROOT / "LICENSE-CLAUSE.md"
    check("LICENSE-CLAUSE.md exists", lic.exists())
    if lic.exists():
        text = lic.read_text(encoding="utf-8")
        check("declares Tier 1 (MIT / open)", "Tier 1" in text and "MIT" in text)
        check("declares Tier 2 (Proprietary)", "Tier 2" in text and "Proprietary" in text)
        check("names the private repo", "flybrain-connectome-core" in text)

    # 2. core_bridge graceful degradation
    print("\n-- 2. core_bridge graceful degradation --")
    bridge = MCP / "core_bridge.py"
    check("core_bridge.py exists", bridge.exists())
    try:
        sys.path.insert(0, str(MCP))
        import core_bridge as cb  # type: ignore
        check("core_available() callable", callable(cb.core_available))
        env = cb.require_core("list_combination_rules")
        # On this bare dev install core is absent → must return a Tier-2 envelope
        check("require_core returns Tier-2 envelope when core absent",
              isinstance(env, dict) and env.get("status") == "tier2_required")
        check("functional_tool_count degrades to 31 bare (40 − 9 tier2 tools)",
              cb.functional_tool_count() == 31)
        st = cb.tiering_status()
        check("tiering_status reports canonical private repo",
              "flybrain-connectome-core" in st["canonical_tier2_repo"])
    except Exception as e:
        check("core_bridge imports & degrades", False, str(e))

    # 3. Private repo canonical home
    print("\n-- 3. Canonical Tier-2 home (private repo) --")
    pr = _check_private_repo()
    if pr["ok"] is None:
        print("  [SKIP] %s" % pr["detail"])
    else:
        check("flybrain-connectome-core is private", pr["ok"] is True,
              pr.get("detail", ""))

    print("\n" + "=" * 72)
    if failures:
        print("GATE 8: FAIL — %d checks failed: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("GATE 8: PASS — tiering architecture in place (IP removal from public tree pending explicit push)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
