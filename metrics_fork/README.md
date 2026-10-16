# metrics_fork — Read-Only Metrics Fork

**Purpose.** This subdirectory is the **minimal public-facing fork** of the
`flybrain-connectome` project. It exists so that the methodological short paper
published alongside this repository has a concrete, independently re-runnable
evidence base for its traceability claims.

**What is here (all read-only, all data-optional, no engine, no keys):**

```
metrics_fork/
├── README.md                  ← this file · fork rules + how to re-run
├── LICENSE                    ← Apache-2.0 (more permissive than upstream MIT)
├── data_manifest.json         ← external dataset pointers (URLs, versions,
│                                checksums) — no data files in this repo
└── metrics/
    ├── __init__.py
    ├── robustness.py          ← F4a · intervention & bridge-fraction metrics
    ├── controllability.py     ← F1  · reachability & control-set metrics
    └── recovery.py            ← F2  · recovery-AUC & drop-magnitude metrics
```

**What is NOT here, and why:**

| Not here | Where it lives | Why it stays out |
|---|---|---|
| Main engine (`flybrain-connectome-mcp/`) | upstream repo | Not required to reproduce the paper's numbers; keeping the fork tiny and stable |
| MaleCNS v1.0 data (~5.63 GB) | `male-cns.janelia.org/download`, CC-BY | Referenced by URL + checksum only; the paper reports derived figures, not raw weights |
| C. elegans / larva connectomes | `DATA_MANIFEST.json` | Same — pointers only |
| LLM orchestrator & prompt traces | upstream repo | Paper does not depend on LLM access; keeps the fork offline-verifiable |
| Secrets, tokens, PATs | never in any git history | Non-negotiable |

## Fork rules

This is a **one-way, read-only fork**. The contract with downstream users is:

1. **Never write back.** Anything added to `metrics_fork/` is a *paper-only*
   artifact. Upstream changes flow in through a periodic resync (below).
2. **No secrets, ever.** The upstream credential gate
   (`scripts/check_no_secrets.py`) must pass on this tree before push.
3. **No data.** Data is referenced by URL + checksum. Data volume and
   redistribution licensing are not this fork's concern.
4. **No engine, no LLM.** The three metric scripts are pure Python
   (`json` + `statistics` + `math` only). No `numpy`, no `networkx`, no
   external service call.
5. **Read-only by construction.** Scripts compute; they do not mutate the
   input graph. `python -m metrics.robustness --graph <g.json> --k 3` returns
   numbers and exits; it does not write files.

## How to re-run a metric

All three metrics accept a graph as a JSON file in this shape:

```json
{
  "nodes": ["n0", "n1", "n2", "n3"],
  "edges": [
    {"from": "n0", "to": "n1", "weight": 0.7},
    {"from": "n1", "to": "n2", "weight": 0.5},
    {"from": "n2", "to": "n3", "weight": 0.9}
  ]
}
```

Any graph that can be reduced to that shape works — including a
`flybrain-connectome` generated organism JSON (which has the same `nodes`/
`edges` top-level fields).

```bash
# From the metrics_fork/ root:

# F4a — bridge-fraction & removal-impact metrics
python -m metrics.robustness --graph path/to/topology.json --k 3

# F1  — control-set size & reachability
python -m metrics.controllability --graph path/to/topology.json

# F2  — recovery-AUC under sequential edge removal
python -m metrics.recovery --graph path/to/topology.json --k 5 --steps 20
```

Each command prints a small JSON object to stdout with the computed metric and
its inputs. It is designed so the printed JSON is the entire result — no log
files, no side effects — so a re-runnability claim can be verified with a
single `diff`.

### Self-contained smoke test (no upstream artifacts needed)

`graphs/sample_topology.json` is a 12-node, 17-edge modular graph (three dense
modules joined by two bridges) shipped *inside this fork*. It exists so the
three metrics can be re-run with zero upstream dependencies — useful as a
smoke test and as a schema reference:

```bash
# From metrics_fork/ root — all three must exit 0 and print JSON:
python -m metrics.robustness      --graph graphs/sample_topology.json --k 3
python -m metrics.controllability --graph graphs/sample_topology.json
python -m metrics.recovery        --graph graphs/sample_topology.json --k 5 --steps 20
```

Expected (stable) headline numbers for this sample: robustness →
`n_components_before = n_components_after = 1`, `removal_drop_per_edge = 0.9`;
controllability → `n_control_nodes_bound = 2`, `reachability_fraction ≈ 0.727`;
recovery → `variance_of_deltas ≈ 3.898e-05`.

## Re-running the paper's numbers

The methodology paper (`docs/arxiv_methodology_short_paper_2026-10-16.md` in
the upstream repo) reports three sets of numbers that come out of these three
scripts. Each claim is reproduced from a *graph-shaped* input; the upstream
experiment directories (`_f4_intervention_n100/`, `_f2_recovery/`, …) contain
**result artifacts** (`{"summary", "all_results"}`) that must first be
exported to the `{"nodes", "edges"}` shape before these scripts can read them.

| Paper claim | Script | Graph input (this fork) | Upstream artifact | Command (self-contained) |
|---|---|---|---|---|
| §5.2 F4a bridge fraction | `metrics/robustness.py` | `graphs/sample_topology.json` | `_f4_intervention_n100/f4_intervention.json` (result, not graph) | `python -m metrics.robustness --graph graphs/sample_topology.json --k 3` |
| §5.3 F1 control-set size | `metrics/controllability.py` | `graphs/sample_topology.json` | *(no upstream artifact at this path)* | `python -m metrics.controllability --graph graphs/sample_topology.json` |
| §5.4 F2 recovery AUC | `metrics/recovery.py` | `graphs/sample_topology.json` | `_f2_recovery/f2_recovery_dynamics.json` (result, not graph) | `python -m metrics.recovery --graph graphs/sample_topology.json --k 5 --steps 20` |

**Reproducibility status (as of v2.94.0).** The three commands above are the
only ones that exit 0 against a self-contained input shipped inside this fork.
A reader who wants to re-derive the *paper's exact numbers* must first:

1. Pull the upstream result artifact (via `DATA_MANIFEST.json` checksums).
2. Export it to the graph shape — this is a **separate, not-yet-shipped**
   export step. The upstream repo does not currently ship a
   result→graph exporter, so the paper's headline numbers cannot yet be
   reproduced verbatim from this fork.
3. Run the three commands against the exported graph and diff the JSON
   output against the paper's table.

**Gate 54** (`scripts/check_metrics_fork.py` in the upstream repo) enforces
that the three self-contained commands above keep exiting 0 with valid JSON,
so the smoke-test portion of this table is machine-checked, not just asserted.
The upstream-artifact column is informational only; it is not machine-checked.

> **v2.94.0 fix.** Earlier versions of this README pointed at non-existent
> paths (`_f4_intervention_n100/artifact.json`, `generated_organisms/pcv2_5x8.json`,
> `_f2_recovery/artifact.json`) — those files do not exist, and even the
> correct upstream result files (`f4_intervention.json`,
> `f2_recovery_dynamics.json`) are result artifacts, not graph files, so the
> commands raised `KeyError: 'edges'`. The table above is the corrected
> version: the self-contained column is what actually runs; the upstream
> column is labelled as result-not-graph and not runnable verbatim.

## Version & sync policy

- Fork version is bumped in lockstep with the paper (v0.1 = this commit).
- Upstream releases trigger a manual resync; the resync is one-way:
  upstream changes may be **reduced** into this fork, never the other way
  around.
- Fork history is separate. If `metrics_fork/` is ever published as a
  standalone repository, its commit history starts fresh from this tag.
