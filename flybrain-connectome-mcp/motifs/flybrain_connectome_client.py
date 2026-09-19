"""
flybrain_connectome_client.py
------------------------------
Drop-in client for SwarmLabs (or ANY other project) to call the
flybrain-connectome service WITHOUT embedding the 166,700-neuron data.

Two transport options (both keep flybrain independent):

  A) HTTP API  (recommended for non-MCP callers)
     Start the server once:
         FLYBRAIN_DATA_DIR=.../male_cns python -m mcp_connectome.api_server
     Then use FlybrainHTTPClient(base_url, api_key).

  B) MCP stdio (if your runtime speaks MCP)
     Add the server entry (see SWARMLABS_INTEGRATION.md) to your mcp config;
     the tools are identical to the HTTP ones.

All raw helpers return the service ENVELOPE
    {"ok": true, "tool": "<name>", "result": <payload>}
Use `.query(tool, args)` to get the unwrapped payload, or the typed helpers
(`pair_synapses`, `export_swarm_motifs`, ...) which unwrap for you.

Example
-------
    from flybrain_connectome_client import FlybrainHTTPClient, build_agent_topology

    c = FlybrainHTTPClient("http://127.0.0.1:8799")   # key from FLYBRAIN_API_KEY env
    print(c.pair_synapses(10540, 12569))              # -> 711
    motifs = c.export_swarm_motifs()                  # -> full derived motif doc
    topo = build_agent_topology(motifs["motifs"]["inhibitory_hub"], K_workers=12)
    # topo = {"pattern":.., "nodes":[...], "edges":[{"from":..,"to":..,"weight":..,"kind":..}]}

Offline motif builds (`build_agent_topology`) need NO server and NO key.
"""
from __future__ import annotations
import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = os.environ.get("FLYBRAIN_API_URL", "http://127.0.0.1:8799")

# ---- real tool names exposed by the service (do not invent) ----
TOOL_NAMES = [
    "connectome_overview", "neuron_info", "pair_synapses", "neuron_outputs",
    "neuron_inputs", "degree", "search_neurons", "superclass_projection",
    "hub_targets", "list_superclasses", "pathway",
    "export_swarm_motifs",
]


class FlybrainUnavailable(RuntimeError):
    """Raised when the flybrain service cannot be reached or rejects the call.

    Callers that want a graceful degradation (e.g. C1's `auto` motif source)
    should catch THIS, not bare Exception.

    `auth=True` marks a *configuration* failure (401/403) rather than an
    availability failure. Callers should NOT silently fall back on those —
    a wrong/missing API key is a mistake you want to see, not paper over.
    """

    def __init__(self, message: str, auth: bool = False):
        super().__init__(message)
        self.auth = bool(auth)


class FlybrainHTTPClient:
    def __init__(self, base_url: str | None = None,
                 api_key: str | None = None, timeout: int = 120):
        """api_key resolves from the argument, else env FLYBRAIN_API_KEY.
        Offline motif builds (build_agent_topology) need NO key.
        Real-time query requires the flybrain API server up + a valid key."""
        self.base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.key = api_key if api_key is not None else os.environ.get("FLYBRAIN_API_KEY", "")
        self.timeout = int(timeout)

    # ------------------------------------------------------------------ #
    # transport
    # ------------------------------------------------------------------ #
    def call(self, tool: str, args: dict | None = None) -> dict:
        """POST /query and return the raw service envelope."""
        req = urllib.request.Request(
            self.base + "/query",
            data=json.dumps({"tool": tool, "args": args or {}}).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            if e.code in (401, 403):
                raise FlybrainUnavailable(
                    "auth rejected (%d): %s" % (e.code, raw[:200]),
                    auth=True) from e
            try:
                return json.loads(raw)
            except Exception:  # noqa: BLE001
                raise FlybrainUnavailable("HTTP %d: %s" % (e.code, raw[:200])) from e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise FlybrainUnavailable(
                "cannot reach %s (%s)" % (self.base, e)) from e

    def query(self, tool: str, args: dict | None = None):
        """POST /query and return the UNWRAPPED result payload.

        Raises FlybrainUnavailable on transport error or {"ok": false}.
        """
        env = self.call(tool, args)
        if not isinstance(env, dict) or not env.get("ok"):
            err = env.get("error") if isinstance(env, dict) else env
            raise FlybrainUnavailable("tool %s failed: %s" % (tool, err))
        return env.get("result")

    # backwards-compatible alias: old code called `. _post(tool, args)` and got
    # the raw envelope back (which is exactly what `call` does).
    def _post(self, tool: str, args: dict | None = None) -> dict:
        return self.call(tool, args)

    def health(self) -> dict:
        try:
            with urllib.request.urlopen(self.base + "/health", timeout=5) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise FlybrainUnavailable("health check failed: %s" % e) from e

    def is_up(self) -> bool:
        try:
            self.health()
            return True
        except FlybrainUnavailable:
            return False

    # --- typed helpers (mirror the MCP tools) — unwrapped payloads ---
    def overview(self):                 return self.query("connectome_overview")
    def neuron_info(self, body):        return self.query("neuron_info", {"body": body})
    def pair_synapses(self, pre, post): return self.query("pair_synapses", {"pre": pre, "post": post})
    def neuron_outputs(self, body, top=20): return self.query("neuron_outputs", {"body": body, "top": top})
    def neuron_inputs(self, body, top=20):  return self.query("neuron_inputs", {"body": body, "top": top})
    def degree(self, body):             return self.query("degree", {"body": body})
    def search_neurons(self, q, field="type", limit=20):
        return self.query("search_neurons", {"query": q, "field": field, "limit": limit})
    def superclass_projection(self, sc): return self.query("superclass_projection", {"superclass": sc})
    def hub_targets(self, name):        return self.query("hub_targets", {"name": name})
    def list_superclasses(self):        return self.query("list_superclasses")
    def pathway(self, source, target, max_via=1):
        return self.query("pathway", {"source": source, "target": target, "max_via": max_via})

    def export_swarm_motifs(self, refresh: bool = False) -> dict:
        """Runtime pull of the derived SwarmLabs motif document.

        Returns the full motif JSON (same shape as
        `motifs/swarm_agent_topology_motifs.json`), fetched live from the
        service. `refresh=True` asks the service to re-run extract_motifs.py
        first so the caller always gets the freshest derived artifact.

        Only the DERIVED description comes back — never the 166,700 raw neurons.
        """
        return self.query("export_swarm_motifs", {"refresh": bool(refresh)})

    def tools(self) -> list:
        """GET /tools — names + descriptions, requires a valid key."""
        req = urllib.request.Request(
            self.base + "/tools",
            headers={"Authorization": "Bearer " + self.key})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")).get("tools", [])
        except urllib.error.HTTPError as e:
            raise FlybrainUnavailable("cannot list tools: HTTP %d" % e.code,
                                      auth=e.code in (401, 403)) from e
        except Exception as e:  # noqa: BLE001
            raise FlybrainUnavailable("cannot list tools: %s" % e) from e


# ---------------------------------------------------------------------- #
# module-level convenience (no instance needed)
# ---------------------------------------------------------------------- #
def resolve_local_api_key(config_path: str | os.PathLike | None = None) -> tuple[str, str]:
    """Last-resort, SAME-MACHINE key discovery.

    Reads `api_keys[0]` from the service's own `mcp_connectome/config.json`
    (default: ../mcp_connectome/config.json relative to this file).

    This exists ONLY so that callers living inside the flybrain project can talk
    to their own local service without exporting an env var on every shell.
    A downstream project consumes this module as a drop-in copy elsewhere, where
    this file does not exist — so the lookup returns ("", "none") and the caller
    must pass a key explicitly. Precedence is always: explicit arg -> env -> here.

    Returns (key, source) with source in {"local_config", "none"}.
    """
    p = Path(config_path) if config_path else (
        Path(__file__).resolve().parent.parent / "mcp_connectome" / "config.json")
    try:
        with open(p, encoding="utf-8") as fh:
            keys = json.load(fh).get("api_keys") or []
        if keys:
            return str(keys[0]), "local_config"
    except (OSError, ValueError):
        pass
    return "", "none"


def fetch_motifs_via_api(base_url: str | None = None, api_key: str | None = None,
                         refresh: bool = False, timeout: int = 120) -> dict:
    """One-shot runtime pull of the derived motif doc from the service."""
    return FlybrainHTTPClient(base_url, api_key, timeout=timeout)\
        .export_swarm_motifs(refresh=refresh)


# ---------------------------------------------------------------------- #
# motif -> agent topology (offline, pure)
# ---------------------------------------------------------------------- #
def build_agent_topology(motif: dict, K_workers: int = 12, seed: int = 0):
    """Translate a flybrain MOTIF (from swarm_agent_topology_motifs.json) into a
    minimal agent-graph spec SwarmLabs can instantiate.

    Returns {"pattern", "nodes", "edges"} where edges carry a normalized weight
    and a biological 'kind' (inhibitory / recurrent / reservoir).
    """
    rng = random.Random(seed)
    pattern = motif.get("pattern")
    nodes = []

    if pattern == "inhibitory_hub":
        coord = {"id": "coordinator", "role": "guardrail",
                 "source": "APL(body %d)" % motif.get("hub_body")}
        nodes.append(coord)
        targets = motif.get("broadcast_targets", [])[:K_workers]
        max_s = max((t["synapses"] for t in targets), default=1) or 1
        edges = []
        for t in targets:
            w = round(t["synapses"] / max_s, 3)          # normalized inhibition [0,1]
            edges.append({"from": "coordinator", "to": "worker_%d" % t["body"],
                          "weight": -w, "kind": "inhibitory",
                          "ref_body": t["body"], "ref_type": t.get("type")})
            nodes.append({"id": "worker_%d" % t["body"], "role": "worker",
                          "ref_body": t["body"], "ref_type": t.get("type")})
        return {"pattern": pattern, "nodes": nodes, "edges": edges}

    if pattern == "reservoir_smallworld":
        # Preserve the fly's DEGREE-SHAPE but scale it to a K-agent reservoir.
        # (Real buckets go up to 10000+ synapses; a 10-agent reservoir can't have
        #  that many edges, so we map each bucket's relative position onto [0, K-1].)
        dist = motif.get("fanout_distribution_pct", {})
        buckets = [("1-10", 1, 10), ("11-100", 11, 100), ("101-1000", 101, 1000),
                   ("1001-10000", 1001, 10000), ("10000+", 10001, 20000)]
        weights = [dist.get(b[0], 0) or 0 for b in buckets]
        tot = sum(weights) or 1
        NORM = 20000.0  # top of the scale, used to normalize relative degree
        nodes = [{"id": "r%d" % i, "role": "reservoir"} for i in range(K_workers)]
        edges = []
        for n in nodes:
            pick = rng.choices(buckets, weights=[w / tot for w in weights])[0]
            lo, hi = pick[1], pick[2]
            rel = rng.uniform(lo, hi) / NORM          # relative out-degree in [0,1]
            deg = int(round(rel * K_workers))
            deg = max(0, min(deg, K_workers - 1))      # never empty-range
            if deg <= 0:
                continue
            for t in rng.sample(nodes, deg):
                if t["id"] != n["id"]:
                    edges.append({"from": n["id"], "to": t["id"],
                                  "weight": round(rng.random(), 3), "kind": "reservoir"})
        return {"pattern": pattern, "nodes": nodes, "edges": edges}

    if pattern == "recurrent_feedback":
        loops = motif.get("self_recurrence_top", [])[:K_workers]
        nodes = [{"id": "mod_%s" % c["superclass"], "role": "module",
                  "ref_superclass": c["superclass"]} for c in loops]
        edges = []
        for c in loops:
            w = round(min(c.get("pct_of_total", 0) / 100.0, 1.0), 3)
            edges.append({"from": "mod_%s" % c["superclass"],
                          "to": "mod_%s" % c["superclass"],
                          "weight": w, "kind": "recurrent"})
        return {"pattern": pattern, "nodes": nodes, "edges": edges}

    raise ValueError("unknown motif pattern: %r" % pattern)


if __name__ == "__main__":
    # self-test: load local motif, build all three topologies
    here = os.path.dirname(os.path.abspath(__file__))
    m = json.load(open(os.path.join(here, "swarm_agent_topology_motifs.json"),
                       encoding="utf-8"))
    for name, mot in m["motifs"].items():
        topo = build_agent_topology(mot, K_workers=10)
        print(name, "-> nodes=%d edges=%d" % (len(topo["nodes"]), len(topo["edges"])))
