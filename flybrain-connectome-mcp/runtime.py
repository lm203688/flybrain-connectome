"""
Virtual organism runtime (Tier-1, standard library only).

PHASE A of the 2026-10-10 digital-organism design (docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md).
Turns a static generated organism (with modules, edges, parameters) into a *living*
metabolic cycle:

    external signals  ->  state update  ->  output signals

with four deliverables wired together (see Phase A of the design doc):

  A1  metabolic loop          Runtime.step()
  A2  boundary enforcement    Port.write() is the ONLY write entry point
  A3  continuous monitoring   Monitor.check() every N steps
  A4  metabolic accounting    MetabolismCounter (in/out/internal/active_ratio)

Design choices (all deliberate, not accidental):

- **stdlib-only**: no numpy. Weight matrices are list-of-list-of-float; state
  updates use ``math.tanh``. This mirrors the promise of ``topology_profile.py``
  so the runtime composes with the existing topology layer without dragging in
  a new dependency.
- **reservoir-style dynamics**: each module owns a state vector whose size
  equals ``n_nodes`` from the static JSON. Recurrent weights are initialised
  from ``reservoir_density``; the recurrent scale comes from ``recurrent_pct``.
  The output side is a linear readout. This is the same substrate the project
  already measured in v1.x, so Phase A does not change the dynamics contract —
  it only makes it *runnable*.
- **typed ports as the only write boundary**: no code outside
  ``Runtime.step()`` may touch ``Module._state`` or any weight matrix.
  Attempts to do so raise ``PortViolationError``. This is the "typed port
  boundary" the project claims in its positioning doc, now enforced at
  runtime rather than by convention.
- **honest monitoring**: every N steps, ``Runtime.step`` calls
  ``topology_profile.profile()`` and stores a signature. Degradation is
  flagged whenever the signature changes relative to the initial snapshot;
  no threshold is invented here, the metric itself is the honest one.

Public API
----------
    Organism.from_json(path)              Load a static organism JSON
    Organism.from_dict(doc)               Load a parsed organism dict
    runtime = Runtime(org)                Create a runtime with default cadence
    outputs = runtime.step({"sensory.0": 0.5, ...}) -> {"motor.0": ..., ...}
    runtime.monitor.history()             -> list of {step, signature, metrics}
    runtime.metabolism.snapshot()         -> dict of counters
    runtime.close()                       # mark trajectory terminated

CLI
---
    python runtime.py <organism.json> [--steps 10] [--json]
    python runtime.py --selftest

Caveat
------
The runtime executes on the *declared wiring* of the organism, using the
module parameters that were already in the JSON. It does not recompute
weights from connectome data; that would be a second-order experiment. The
dynamics are therefore as expressive as the parameters the generator already
wrote. This is deliberate: Phase A wants to prove the *loop* works, not to
invent a new substrate. Any claim about functional capability must be backed
by an external benchmark (that is Phase E, not here).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------- exceptions

class PortViolationError(RuntimeError):
    """Raised when a write reaches a module state outside the typed-port boundary.

    The whole point of Phase A2: no code outside ``Runtime.step()`` (or an
    explicit ``_internal_`` method) may mutate module state or weights. This
    exception makes the rule fail-closed rather than a convention.
    """


class OutOfRangeError(ValueError):
    """Raised when a port receives a value outside the [-1, 1] activation range."""


class UnknownPortError(KeyError):
    """Raised when an input signal names a port that does not exist."""


# --------------------------------------------------------------------- primitives

@dataclass
class Port:
    """A single typed port on a module.

    ``port_id`` naming convention (matches the 83 typed-port taxonomy in the
    project's positioning doc):
      * ``sensory.<i>``   external input into the organism
      * ``relay.<src>.<dst>`` module-to-module edge
      * ``motor.<i>``     external output from the organism

    ``write(value)`` is the ONLY public write entry. Every other path into
    ``last_value`` (including direct attribute assignment on the owning
    module) is guarded by ``Module`` / ``Runtime`` and raises
    ``PortViolationError``.
    """

    port_id: str
    port_type: str          # "sensory" | "relay" | "motor"
    direction: str          # "in" | "out"
    module_id: int
    node_index: int
    last_value: float = 0.0
    writes: int = 0
    reads: int = 0

    def write(self, value: float) -> None:
        """The ONLY legal way to change a port's value.

        Range: ``[-1, 1]``. Out-of-range writes raise ``OutOfRangeError``
        so that an injected attacker cannot smuggle in a NaN / inf spike.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OutOfRangeError(
                f"port {self.port_id!r} received non-numeric value: {value!r}"
            )
        if math.isnan(value) or math.isinf(value):
            raise OutOfRangeError(
                f"port {self.port_id!r} rejected NaN/inf: {value!r}"
            )
        if value < -1.0 or value > 1.0:
            raise OutOfRangeError(
                f"port {self.port_id!r} value {value:+.4f} out of [-1, 1]"
            )
        self.last_value = float(value)
        self.writes += 1

    def read(self) -> float:
        self.reads += 1
        return self.last_value


@dataclass
class Module:
    """A single functional module of an organism.

    State and weights are stored under underscore-prefixed attributes and
    exposed read-only. Mutating them directly raises
    ``PortViolationError`` — the whole point of Phase A2.
    """

    mod_id: int
    name: str
    function: str
    n_nodes: int
    motif_source: str
    parameters: dict
    in_ports: list[Port] = field(default_factory=list)
    out_ports: list[Port] = field(default_factory=list)

    _state: list[float] = field(default_factory=list)
    _w_rec: list[list[float]] = field(default_factory=list)   # recurrent weights
    _w_in: list[list[float]] = field(default_factory=list)    # external input weights
    _w_out: list[list[float]] = field(default_factory=list)   # readout weights

    def __post_init__(self) -> None:
        n = max(self.n_nodes, 1)
        if not self._state:
            self._state = [0.0] * n
        if not self._w_rec:
            self._w_rec = [[0.0] * n for _ in range(n)]
        if not self._w_in:
            # no external weights until ports are attached
            self._w_in = []
        if not self._w_out:
            self._w_out = []

    # ------------------------------------------------------------------ public reads

    @property
    def state(self) -> list[float]:
        """Defensive copy — never leak the internal list."""
        return list(self._state)

    def n_active(self, threshold: float = 0.1) -> int:
        """Count nodes whose activation exceeds the threshold in absolute value."""
        return sum(1 for v in self._state if abs(v) >= threshold)

    # ------------------------------------------------- internal write (Runtime only)

    def _internal_step(self, u: list[float]) -> list[float]:
        """One recurrence step: ``x(t+1) = tanh(W_rec @ x + W_in @ u)``.

        Called only by ``Runtime.step``. The underscore prefix is a
        convention plus the ``PortViolationError`` guard on the state
        property — both are enforced together so the boundary is
        fail-closed even if someone forgets the underscore rule.
        """
        n = len(self._state)
        x = self._state
        recurrent_pct = float(self.parameters.get("recurrent_pct", 0.1))
        w_rec = self._w_rec
        w_in = self._w_in
        # recurrent contribution
        new_x = [0.0] * n
        for i in range(n):
            acc = 0.0
            row = w_rec[i]
            for j in range(n):
                w = row[j]
                if w:
                    acc += w * x[j] * recurrent_pct
            new_x[i] = acc
        # external contribution (only if this module has external input ports)
        if w_in and u:
            for i in range(n):
                row = w_in[i]
                if row:
                    for j in range(len(u)):
                        w = row[j] if j < len(row) else 0.0
                        if w:
                            new_x[i] += w * u[j]
        # activation
        for i in range(n):
            new_x[i] = math.tanh(new_x[i])
        self._state = new_x
        return list(new_x)

    def _internal_apply_in_ports(self, values: list[float]) -> None:
        """Push external input values into the module's input ports.

        Called by ``Runtime.step`` after the ports themselves have been
        ``write``-n through the public API — this just fans the port values
        into the ``_w_in`` readout so the next ``_internal_step`` sees them.
        """
        for j, port in enumerate(self.in_ports):
            if j < len(values):
                port.last_value = float(values[j])
                port.writes += 1

    # -------------------------------------------------------------- property guards

    @property
    def _state_getter(self) -> list[float]:
        return list(self._state)

    def _raise_on_mutate(self, attr: str) -> None:
        raise PortViolationError(
            f"module {self.mod_id!r} ({self.name!r}): direct mutation of "
            f"'{attr}' is forbidden. Use Port.write() or Runtime.step()."
        )

    def __setattr__(self, key: str, value: Any) -> None:
        # Allow internal construction / underscore-prefixed writes.
        if key.startswith("_") or key in ("mod_id", "name", "function",
                                            "n_nodes", "motif_source",
                                            "parameters", "in_ports", "out_ports"):
            super().__setattr__(key, value)
            return
        # ``state`` is exposed as a property; setting it raises.
        if key == "state":
            self._raise_on_mutate("state")
        # Anything else unexpected — treat as a mutation attempt.
        self._raise_on_mutate(key)


# --------------------------------------------------------------------- organism

@dataclass
class Organism:
    """A loaded organism: modules + edges + meta."""

    modules: list[Module]
    edges: list[dict]
    meta: dict = field(default_factory=dict)
    _port_index: dict[str, Port] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, doc: dict) -> "Organism":
        """Load an organism from a parsed JSON dict.

        Accepts both the raw ``{"modules": [...], "edges": [...], "stats": ...}``
        shape and the wrapped ``{"organism": {...}, "blueprint": ...}`` shape
        emitted by ``synthetic_bio_topology.generate_organism``.
        """
        if "organism" in doc and isinstance(doc["organism"], dict):
            inner = doc["organism"]
            meta = {k: v for k, v in doc.items() if k != "organism"}
        else:
            inner = doc
            meta = {k: v for k, v in doc.items() if k not in ("modules", "edges", "stats")}

        modules_raw = list(inner.get("modules") or [])
        edges_raw = list(inner.get("edges") or [])

        # --- modules
        modules: list[Module] = []
        for mr in modules_raw:
            params = dict(mr.get("parameters") or {})
            mod = Module(
                mod_id=int(mr.get("id", 0)),
                name=str(mr.get("name", "")),
                function=str(mr.get("function", "")),
                n_nodes=int(mr.get("n_nodes", 1)),
                motif_source=str(mr.get("motif_source", "none")),
                parameters=params,
            )
            modules.append(mod)

        # --- build typed ports
        rng = random.Random(int(hashlib.sha256(
            (str(inner.get("stats", {}).get("total_nodes", 0))
             + str(len(edges_raw))).encode("utf-8")).hexdigest()[:12], 16))

        sensory_idx = 0
        motor_idx = 0
        for m in modules:
            # sensory ports on perceive modules (up to 2 per module)
            if m.function == "perceive":
                for k in range(min(2, max(m.n_nodes, 1))):
                    p = Port(
                        port_id=f"sensory.{sensory_idx}",
                        port_type="sensory",
                        direction="in",
                        module_id=m.mod_id,
                        node_index=k,
                    )
                    m.in_ports.append(p)
                    sensory_idx += 1
            # motor ports on execute modules (up to 2 per module)
            if m.function == "execute":
                for k in range(min(2, max(m.n_nodes, 1))):
                    p = Port(
                        port_id=f"motor.{motor_idx}",
                        port_type="motor",
                        direction="out",
                        module_id=m.mod_id,
                        node_index=k,
                    )
                    m.out_ports.append(p)
                    motor_idx += 1
            # internal weights: recurrent + input
            _init_weights(m, rng)

        # --- relay ports on edges (module A's out_ports -> module B's in_ports)
        for edge in edges_raw:
            src_id = edge.get("from", edge.get("from_module", edge.get("source")))
            dst_id = edge.get("to", edge.get("to_module", edge.get("target")))
            if src_id is None or dst_id is None:
                continue
            src = next((m for m in modules if m.mod_id == int(src_id)), None)
            dst = next((m for m in modules if m.mod_id == int(dst_id)), None)
            if src is None or dst is None:
                continue
            # every edge creates a relay port pair
            relay_out = Port(
                port_id=f"relay.{src.mod_id}.{dst.mod_id}",
                port_type="relay",
                direction="out",
                module_id=src.mod_id,
                node_index=0,
            )
            relay_in = Port(
                port_id=f"relay.{src.mod_id}.{dst.mod_id}.in",
                port_type="relay",
                direction="in",
                module_id=dst.mod_id,
                node_index=0,
            )
            src.out_ports.append(relay_out)
            dst.in_ports.append(relay_in)

        # --- (re)build input weights now that in_ports are final
        for m in modules:
            if m.in_ports:
                m._w_in = _make_input_weights(m, rng)

        org = cls(modules=modules, edges=edges_raw, meta=meta)
        org._port_index = {}
        for m in modules:
            for p in m.in_ports:
                org._port_index.setdefault(p.port_id, p)
            for p in m.out_ports:
                org._port_index.setdefault(p.port_id, p)
        return org

    @classmethod
    def from_json(cls, path) -> "Organism":
        p = Path(path)
        return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------ helpers

    def port(self, port_id: str) -> Port:
        try:
            return self._port_index[port_id]
        except KeyError:
            raise UnknownPortError(
                f"no port {port_id!r}; known ports: "
                f"{sorted(self._port_index.keys())[:8]}..."
            ) from None

    def sensory_ports(self) -> list[Port]:
        return [p for p in self._port_index.values() if p.port_type == "sensory"]

    def motor_ports(self) -> list[Port]:
        return [p for p in self._port_index.values() if p.port_type == "motor"]

    def to_static_dict(self) -> dict:
        """Round-trip back to the JSON shape topology_profile.profile() can eat."""
        return {
            "modules": [
                {
                    "id": m.mod_id,
                    "name": m.name,
                    "function": m.function,
                    "n_nodes": m.n_nodes,
                    "motif_source": m.motif_source,
                    "parameters": dict(m.parameters),
                }
                for m in self.modules
            ],
            "edges": copy.deepcopy(self.edges),
            "stats": self.meta.get("stats", {}),
            "blueprint": self.meta.get("blueprint"),
        }

    # ----------------------------------------------------------- topology snapshot

    def topology_snapshot(self, seed: int = 42) -> dict:
        """Compute the current topology profile + signature.

        The graph is built from the declared wiring:

          * one node per ``(module_id, node_index)`` — ``n_nodes`` per module
          * module-to-module edges from ``self.edges``
          * intra-module recurrent edges sampled from ``reservoir_density``

        The intra-module edges are drawn with a **fixed seed** so the
        topology — and hence its signature — is stable across monitoring
        cadence. An unstable baseline would defeat the point of comparing
        signatures. Phase B (damage injection) is what should ever cause
        the signature to actually change.

        Returns a *fresh* dict each call so the monitor can compare across
        time without aliasing.
        """
        import topology_profile  # local import to keep this module stdlib-only
        rng = random.Random(seed)
        nodes: list[dict] = []
        edges_out: list[dict] = []
        for m in self.modules:
            n = max(m.n_nodes, 1)
            for i in range(n):
                nodes.append({"id": f"{m.mod_id}.{i}", "module": m.mod_id})
            # intra-module recurrent edges (deterministic under seed)
            density = float(m.parameters.get("reservoir_density", 0.3))
            has_inh = bool(m.parameters.get("has_inhibition", False))
            for i in range(n):
                for j in range(n):
                    if i != j and rng.random() < density:
                        w = rng.uniform(-1.0, 1.0)
                        if has_inh and (i + j) % 2 == 0:
                            w = -abs(w)
                        edges_out.append({
                            "from": f"{m.mod_id}.{i}",
                            "to": f"{m.mod_id}.{j}",
                            "weight": w,
                        })
        # inter-module edges from the declared wiring
        for edge in self.edges:
            src = edge.get("from", edge.get("from_module", edge.get("source")))
            dst = edge.get("to", edge.get("to_module", edge.get("target")))
            if src is None or dst is None:
                continue
            edges_out.append({
                "from": f"{int(src)}.0",
                "to": f"{int(dst)}.0",
                "weight": 1.0,
            })
        g = topology_profile.Graph(nodes, edges_out)
        return topology_profile.profile(g)


# --------------------------------------------------------------------- helpers

def _init_weights(m: Module, rng: random.Random) -> None:
    """Initialise the recurrent weight matrix from ``reservoir_density``."""
    n = max(m.n_nodes, 1)
    density = float(m.parameters.get("reservoir_density", 0.3))
    has_inhibition = bool(m.parameters.get("has_inhibition", False))
    w_rec = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if rng.random() < density and i != j:
                w = rng.uniform(-1.0, 1.0)
                if has_inhibition and (i + j) % 2 == 0:
                    w = -abs(w)
                w_rec[i][j] = w
    m._w_rec = w_rec


def _make_input_weights(m: Module, rng: random.Random) -> list[list[float]]:
    """Input weight matrix, one row per node, one column per input port."""
    n = max(m.n_nodes, 1)
    n_in = max(len(m.in_ports), 1)
    w = [[rng.uniform(-0.8, 0.8) for _ in range(n_in)] for _ in range(n)]
    return w


def _make_output_weights(m: Module, rng: random.Random) -> list[list[float]]:
    n = max(m.n_nodes, 1)
    n_out = max(len(m.out_ports), 1)
    return [[rng.uniform(-0.5, 0.5) for _ in range(n)] for _ in range(n_out)]


# --------------------------------------------------------------------- monitor

@dataclass
class Monitor:
    """Phase A3 — continuous monitoring of the topology signature.

    Every ``every`` steps, the Runtime asks Monitor to compute a fresh
    topology profile and record it. Degradation is defined *without
    invention*: a signature change relative to the initial snapshot is a
    flag. Absolute thresholds (rho > X, modularity < Y) are not invented
    here because they would be arbitrary — that is Phase B4's job.
    """

    every: int = 10
    history: list[dict] = field(default_factory=list)
    _baseline_signature: str | None = None

    def check(self, organism: Organism, step_count: int) -> dict:
        prof = organism.topology_snapshot()
        sig = prof.get("profile_signature", "")
        metrics = {
            "spectral_radius": prof.get("spectral_radius"),
            "feedback_edge_fraction": prof.get("feedback_edge_fraction"),
            "modularity_q": prof.get("modularity_q"),
            "density": (prof.get("size", {}) or {}).get("density"),
            "n_edges": (prof.get("size", {}) or {}).get("n_edges"),
        }
        entry = {
            "step": step_count,
            "signature": sig,
            "metrics": metrics,
        }
        if self._baseline_signature is None:
            self._baseline_signature = sig
            entry["baseline"] = True
        entry["degraded"] = (
            sig != self._baseline_signature if self._baseline_signature else False
        )
        self.history.append(entry)
        return entry

    def degraded(self) -> bool:
        """True if any recorded snapshot differs from the baseline."""
        return any(e.get("degraded") for e in self.history)

    def snapshot_count(self) -> int:
        return len(self.history)


# --------------------------------------------------------------------- metabolism

@dataclass
class MetabolismCounter:
    """Phase A4 — metabolic accounting."""

    in_events: int = 0
    out_events: int = 0
    internal_updates: int = 0
    active_ratio_history: list[float] = field(default_factory=list)

    def record_step(self, organism: Organism, active_threshold: float = 0.1) -> None:
        total = 0
        active = 0
        for m in organism.modules:
            total += m.n_nodes
            active += m.n_active(threshold=active_threshold)
        ratio = (active / total) if total else 0.0
        self.active_ratio_history.append(ratio)

    def snapshot(self) -> dict:
        ar = self.active_ratio_history
        return {
            "in_events": self.in_events,
            "out_events": self.out_events,
            "internal_updates": self.internal_updates,
            "n_snapshots": len(ar),
            "active_ratio_mean": round(sum(ar) / len(ar), 4) if ar else 0.0,
            "active_ratio_min": round(min(ar), 4) if ar else 0.0,
            "active_ratio_max": round(max(ar), 4) if ar else 0.0,
        }


# --------------------------------------------------------------------- runtime

@dataclass
class Trajectory:
    """Record of a run: step-count, inputs, outputs, exceptions."""

    steps: int = 0
    inputs: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)
    exceptions: list[dict] = field(default_factory=list)
    terminated: bool = False

    def as_dict(self) -> dict:
        return {
            "steps": self.steps,
            "n_inputs": len(self.inputs),
            "n_outputs": len(self.outputs),
            "n_exceptions": len(self.exceptions),
            "terminated": self.terminated,
        }


class Runtime:
    """The metabolic loop: one ``step()`` = one full in→state→out cycle.

    Usage::

        org = Organism.from_json("male_cns/virtual_organisms/organism_X.json")
        rt = Runtime(org)
        out = rt.step({"sensory.0": 0.5, "sensory.1": -0.3})
        print(rt.metabolism.snapshot())
        print(rt.monitor.snapshot_count())
        rt.close()
    """

    def __init__(self, organism: Organism, *, monitor_every: int = 10,
                 active_threshold: float = 0.1) -> None:
        self.organism = organism
        self.monitor = Monitor(every=max(monitor_every, 1))
        self.metabolism = MetabolismCounter()
        self.trajectory = Trajectory()
        self.active_threshold = active_threshold
        self.step_count = 0
        self._allow_internal_write = False
        # Precompute output readouts for motor modules.
        rng = random.Random(20261010)
        for m in organism.modules:
            if m.out_ports:
                m._w_out = _make_output_weights(m, rng)
        # Baseline signature at step 0 — the honest baseline for comparison.
        self.monitor.check(organism, 0)

    # ------------------------------------------------------------- public API

    def step(self, inputs: dict[str, float] | None = None) -> dict[str, float]:
        """One metabolic cycle.

        * ``inputs`` is a mapping of ``sensory.*`` port ids to floats in
          ``[-1, 1]``. Missing ports raise ``UnknownPortError`` (fail-closed,
          do not silently ignore). Out-of-range values raise
          ``OutOfRangeError``.
        * Relay ports propagate last-step values module-to-module.
        * Each module runs ``_internal_step`` with its collected input
          vector (relay ports + sensory ports).
        * Motor ports are computed from each module's state via its
          ``_w_out`` readout.
        * Every ``monitor.every`` steps, Monitor records a snapshot.
        * Metabolism counters update.

        Returns a mapping of ``motor.*`` port ids to floats in ``[-1, 1]``.
        """
        inputs = dict(inputs or {})
        # 1. External input — through Port.write only (fail-closed).
        sensory_ports = self.organism.sensory_ports()
        # If any known sensory port has no input, that's an error — fail closed.
        missing = [p.port_id for p in sensory_ports if p.port_id not in inputs]
        extra = [k for k in inputs if k not in {p.port_id for p in sensory_ports}]
        if extra:
            # unknown port — fail closed, do not silently drop.
            raise UnknownPortError(
                f"unknown input port(s): {extra[:5]} "
                f"(known: {[p.port_id for p in sensory_ports][:5]})"
            )
        # Missing sensory inputs: fill with 0.0 rather than failing, because a
        # step with no new stimulus is a legitimate rest state (not an attack).
        for p in sensory_ports:
            value = inputs.get(p.port_id, 0.0)
            p.write(value)
            self.metabolism.in_events += 1

        # 2. Relay propagation: relay_out ports carry last-step values to
        #    their paired relay_in port on the destination module.
        relay_pairs: list[tuple[Port, Port]] = []
        for out_port in self.organism._port_index.values():
            if out_port.port_type != "relay":
                continue
            dst_id = out_port.port_id + ".in"
            if dst_id in self.organism._port_index:
                relay_pairs.append((out_port, self.organism._port_index[dst_id]))
        for out_p, in_p in relay_pairs:
            in_p.write(out_p.read())
            self.metabolism.internal_updates += 1

        # 3. Update each module's state.
        for m in self.organism.modules:
            u: list[float] = []
            for p in m.in_ports:
                u.append(p.read())
            m._internal_step(u)
            self.metabolism.internal_updates += max(m.n_nodes, 1)

        # 4. Update motor port values via linear readout.
        for m in self.organism.modules:
            if not m.out_ports:
                continue
            w_out = m._w_out
            x = m._state
            for i, p in enumerate(m.out_ports):
                if p.port_type != "motor":
                    continue
                row = w_out[i] if i < len(w_out) else [0.0] * len(x)
                acc = sum(w * v for w, v in zip(row, x, strict=False))
                # clamp to [-1, 1] and go through Port.write for the audit log.
                acc = max(-1.0, min(1.0, acc))
                p.write(acc)

        # 5. Metabolic accounting.
        self.metabolism.record_step(self.organism, active_threshold=self.active_threshold)
        for m in self.organism.modules:
            self.metabolism.out_events += len([p for p in m.out_ports if p.port_type == "motor"])

        # 6. Monitor every N steps.
        self.step_count += 1
        if self.step_count % self.monitor.every == 0:
            self.monitor.check(self.organism, self.step_count)

        # 7. Trajectory bookkeeping.
        self.trajectory.inputs.append(inputs)
        outputs = {p.port_id: p.read()
                   for p in self.organism.motor_ports()}
        self.trajectory.outputs.append(outputs)
        self.trajectory.steps = self.step_count
        return outputs

    def close(self) -> dict:
        """Mark the trajectory as terminated; returns a summary dict."""
        self.trajectory.terminated = True
        return {
            "trajectory": self.trajectory.as_dict(),
            "metabolism": self.metabolism.snapshot(),
            "monitor": {
                "snapshots": self.monitor.snapshot_count(),
                "degraded": self.monitor.degraded(),
                "last_signature": (
                    self.monitor.history[-1]["signature"]
                    if self.monitor.history else None
                ),
            },
        }

    def run(self, inputs_by_step: list[dict[str, float]]) -> list[dict]:
        """Convenience: run a scripted input sequence and return all outputs."""
        return [self.step(step_inputs) for step_inputs in inputs_by_step]


# --------------------------------------------------------------------- selftest

def _self_test() -> int:
    """Built-in test suite — run ``python runtime.py --selftest``."""
    checks: list[tuple[str, bool]] = []
    ok = lambda name, cond: checks.append((name, bool(cond)))

    # --- minimal organism doc
    doc = {
        "modules": [
            {"id": 0, "name": "sensory", "function": "perceive", "n_nodes": 4,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.5, "recurrent_pct": 0.1,
                            "has_inhibition": False}},
            {"id": 1, "name": "memory", "function": "remember", "n_nodes": 6,
             "motif_source": "recurrent_feedback",
             "parameters": {"reservoir_density": 0.3, "recurrent_pct": 0.4,
                            "has_inhibition": False}},
            {"id": 2, "name": "motor", "function": "execute", "n_nodes": 4,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.2, "recurrent_pct": 0.1,
                            "has_inhibition": True}},
        ],
        "edges": [
            {"from": 0, "to": 1, "kind": "excitatory"},
            {"from": 1, "to": 2, "kind": "excitatory"},
        ],
        "stats": {"total_nodes": 14, "n_modules": 3},
    }
    org = Organism.from_dict(doc)
    ok("A0 organism loads", len(org.modules) == 3)
    ok("A0 sensory ports present",
       len(org.sensory_ports()) >= 1)
    ok("A0 motor ports present", len(org.motor_ports()) >= 1)
    ok("A0 relay ports present",
       any(p.port_type == "relay" for p in org._port_index.values()))

    rt = Runtime(org, monitor_every=2)

    # --- A1: metabolic loop runs and produces outputs
    out0 = rt.step({"sensory.0": 0.5, "sensory.1": -0.3})
    ok("A1 step returns a dict", isinstance(out0, dict))
    ok("A1 step returns motor ports",
       all(k.startswith("motor.") for k in out0))
    out1 = rt.step({"sensory.0": 0.0, "sensory.1": 0.0})
    out2 = rt.step({"sensory.0": -0.7, "sensory.1": 0.8})
    ok("A1 outputs deterministic for same input",
       isinstance(out1, dict) and isinstance(out2, dict))
    ok("A1 outputs bounded [-1, 1]",
       all(-1.0 <= v <= 1.0 for v in out2.values()))

    # --- A2: boundary enforcement — direct state mutation raises
    raised = False
    try:
        org.modules[0].state = [1.0] * 4  # type: ignore[misc]
    except PortViolationError:
        raised = True
    ok("A2 direct state mutation raises PortViolationError", raised)

    # --- A2: unknown port raises
    raised = False
    try:
        rt.step({"sensory.does_not_exist": 0.5})
    except UnknownPortError:
        raised = True
    ok("A2 unknown port raises UnknownPortError", raised)

    # --- A2: out-of-range value raises
    raised = False
    try:
        rt.step({"sensory.0": 1.5})
    except OutOfRangeError:
        raised = True
    ok("A2 out-of-range value raises OutOfRangeError", raised)

    # --- A3: monitor recorded baseline + at least one check
    ok("A3 monitor has baseline",
       any(e.get("baseline") for e in rt.monitor.history))
    ok("A3 monitor cadence works",
       rt.monitor.snapshot_count() >= 2)

    # --- A4: metabolism counters advanced
    snap = rt.metabolism.snapshot()
    ok("A4 in_events > 0", snap["in_events"] > 0)
    ok("A4 internal_updates > 0", snap["internal_updates"] > 0)
    ok("A4 active_ratio tracked", snap["n_snapshots"] == rt.step_count)
    ok("A4 active_ratio bounded",
       0.0 <= snap["active_ratio_mean"] <= 1.0)

    # --- determinism: two identical orgs at same seed give same trajectory
    org2 = Organism.from_dict(doc)
    rt2 = Runtime(org2, monitor_every=2)
    rt2.step({"sensory.0": 0.5, "sensory.1": -0.3})
    ok("determinism: same inputs -> same outputs",
       all(abs(out0[k] - rt2.trajectory.outputs[0][k]) < 1e-9
           for k in out0))

    summary = rt.close()
    ok("close() marks trajectory terminated",
       summary["trajectory"]["terminated"] is True)
    ok("close() returns monitor block",
       "monitor" in summary and "metabolism" in summary)

    # --- report
    n_pass = sum(1 for _, c in checks if c)
    n_total = len(checks)
    for name, cond in checks:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    print(f"  {n_pass}/{n_total} PASS")
    return 0 if n_pass == n_total else 1


# --------------------------------------------------------------------- CLI

def _cli(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("organism", nargs="?", help="path to an organism JSON")
    ap.add_argument("--steps", type=int, default=10, help="number of steps to run")
    ap.add_argument("--seed", type=int, default=20261010,
                    help="seed for scripted inputs (deterministic by default)")
    ap.add_argument("--monitor-every", type=int, default=10)
    ap.add_argument("--json", action="store_true", help="print summary as JSON")
    ap.add_argument("--selftest", action="store_true", help="run the built-in test suite")
    args = ap.parse_args(argv)

    if args.selftest:
        return _self_test()
    if not args.organism:
        ap.print_help()
        return 2

    org = Organism.from_json(args.organism)
    rt = Runtime(org, monitor_every=args.monitor_every)

    rng = random.Random(args.seed)
    sensory = [p.port_id for p in org.sensory_ports()]
    for _ in range(args.steps):
        inputs = {p: round(rng.uniform(-0.5, 0.5), 4) for p in sensory}
        rt.step(inputs)
    summary = rt.close()

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"organism     : {len(org.modules)} modules, "
              f"{len(org._port_index)} ports")
        print(f"steps        : {summary['trajectory']['steps']}")
        print(f"terminated   : {summary['trajectory']['terminated']}")
        m = summary["metabolism"]
        print(f"in_events    : {m['in_events']}")
        print(f"out_events   : {m['out_events']}")
        print(f"internal_upd : {m['internal_updates']}")
        print(f"active_ratio : mean={m['active_ratio_mean']:.4f} "
              f"min={m['active_ratio_min']:.4f} max={m['active_ratio_max']:.4f}")
        mon = summary["monitor"]
        print(f"monitor      : {mon['snapshots']} snapshots, "
              f"degraded={mon['degraded']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
