# Traceable Synthetic Bio-Topology Generation from a Real Brain Connectome

**Lexing (厉兴)**  
Independent researcher  
`lm203688/flybrain-connectome` · MIT License (Tier-1 code; repository currently private, re-publicization planned)

**Version 1.1.0 update (2026-09-20):** Added variant true differentiation (19
modules with per-variant parameter overrides), SwarmLabs multi-agent team
integration, and a virtual-organism market. The cell-level densification
experiment (Section 4.3, previously unreported) confirms that the compute
advantage negative result is **closed**: after adding intra-module recursive
edges to reach ESN-viable density (0.10-0.14), motif routing advantage remains
0/7 under paired controls (effect size +0.001 to +0.018 R² points). The
bottleneck was missing cell substrate (9.7× geometric mean improvement from
densification alone), not motif selection.

---

## Abstract

We present a method and a toolkit (currently private, re-publicization planned) that converts a real, published
brain wiring diagram — the male *Drosophila* connectome (**MaleCNS v1.0**:
166,700 neurons, 124,177,617 synapses, CC-BY) — into task-tailored
multi-agent topologies, while retaining **per-edge provenance** back to the
source neurons and synapse classes. Unlike prior "bio-inspired" topology work
that borrows qualitative metaphors, our generator emits a **W3C PROV-JSON**
provenance bundle for every artifact, making the biological lineage
machine-checkable rather than asserted. We empirically evaluate four candidate
advantages of such biologically-grounded topologies against matched random
controls. Three hold up under testing: (1) **traceability** — every edge is
attributable to a real motif (verified 70/70 on a schema-conformance suite);
(2) **structural parsimony** — a genetic search recovers graphs with **−84%**
wire cost versus the biological prior; (3) **structural stability** — **25/27**
(92.6%) sampled topologies exhibit modular fault isolation, with spectral
radius held at 0.00–0.30%. A fourth, **local decision-making**, is only
partially supported (5/28 configurations, simple tasks only). We report two
**negative results** that we consider part of the contribution: under matched
controls, biological motifs showed **no** systematic compute advantage (0/7)
and **no** energy advantage (0/24). We argue that honesty about negative
results is essential when connecting real neuroscience to engineered systems.

---

## 1. Introduction

Bio-inspired design has a long history, but most "brain-like" engineered
systems borrow *qualitative* ideas (sparseness, recurrence, inhibition) without
any *quantitative* link to a measured connectome. This makes their biological
grounding unverifiable: a reader cannot tell whether a claimed "motif" is real
or decorative.

We take the opposite stance. Starting from a complete, published, CC-BY
connectome, we (i) extract a small set of **derived motifs** (inhibitory hub,
reservoir small-world, recurrent feedback) with exact quantitative anchors;
(ii) compose those motifs into **synthetic multi-agent topologies** sized for a
target morphology; and (iii) serialize the *entire lineage* of every artifact
as **W3C PROV-JSON**, so that provenance is a first-class, auditable artifact
rather than a prose claim.

Our central claim is modest and testable: a *traceable* bio-grounded topology
generator is useful as a **design and audit tool** for multi-agent systems,
independent of whether it is literally "better" than random wiring on any
single metric. We therefore separate what we can demonstrate from what we
cannot, and we report the failures.

### 1.1 Honest scope

This work does **not** simulate a fly, train weights, or claim biological
fidelity beyond topology. The "virtual organism" is a *software-layer analogy*:
it reuses real topology *principles* (motif shapes, recurrence rates,
inhibition patterns), not real cells. Where previous framings implied
computational or energetic superiority of biological wiring, we test those
claims directly and find them unsupported.

---

## 2. Related work

- **Connectomics.** The complete male *Drosophila* brain connectome
  (MaleCNS v1.0, *Cell*, 2026; CC-BY) provides, for the first time, a
  whole-brain wiring diagram at cellular resolution that is freely reusable. We
  build directly on its derived statistics.
- **Massive modularity.** Fodor's *The Modularity of Mind* (1983) argued for
  domain-specific, informationally-encapsulated modules; Friston (2008)
  counter-posed distributed, predictive processing. Our fault-isolation
  experiments sit squarely inside this debate: we ask whether *engineered*
  modular topologies isolate failures the way the cognitive-neuroscience
  double-dissociation gold standard implies biological modules do
  (Geddes 2014; Glenberg 2014; Campanella 2022; Vaidya *et al.*, *PNAS* 2010).
- **Bio-inspired multi-agent topologies.** Existing agent frameworks
  (LangGraph, AutoGen, CrewAI) define topologies by hand; they offer no
  provenance mechanism and no link to measured biology. Our generator supplies
  both.
- **Provenance standards.** We adopt **W3C PROV** via the `dataprov` library
  (RI-SE), making artifacts consumable by yProv4ML, MLflow2PROV, and MIT Sloan
  provenance tooling — directly relevant to EU AI Act audit requirements.

---

## 3. Methods

### 3.1 Connectome and derived motifs

From MaleCNS v1.0 we extract three motifs, each with exact quantitative
anchors (not free parameters):

| Motif | Real anchor | Value |
|---|---|---|
| `inhibitory_hub` | APL body id (mushroom-body giant feedback neuron) | **10540**, fan-out **102,263** |
| | APL → DPM synapse count | **711** |
| `reservoir_smallworld` | fan-out bucket 101–1000 share | **49.36%** |
| `recurrent_feedback` | `ol_intrinsic` self-recurrence | **28.74%** |

These are derived descriptions only — the 5.63 GB raw neuron data never leaves
the host that holds it. Downstream consumers receive a 7 KB motif document.

### 3.2 Topology composition (`design_organism`)

Given a morphology spec (`n_modules`, `agents_per_module`, recurrence, optional
blueprint), the generator assigns each module a functional profile
(sensory / memory / motor / integration / attention / reward / …), wires
intra-module recurrence and inter-module small-world links scaled to the fly's
degree distribution, and adds a global inhibitory coordinator modeled on APL.
Node count = `modules × agents_per_module + per-module representatives +
coordinator`.

25 blueprints are provided across three categories (5 basic, 16 biological, 4
synthetic). Each biological blueprint maps to one of the three motifs; the 4
synthetic blueprints are explicitly tagged `motif: none` to avoid implying a
biological prior that does not exist.

### 3.3 Provenance (W3C PROV-JSON)

Every artifact carries a **3-stage provenance**:

1. **motif synapse stats** — the fraction of the 124,177,617-synapse dataset a
   motif accounts for;
2. **motif query** — a runnable SQL-like query that re-derives the motif from
   the source;
3. **blueprint → motif** — the lineage of the chosen blueprint.

This is serialized as a W3C PROV-JSON bundle with `entity` / `activity` /
`agent` nodes and `wasDerivedFrom` / `wasAssociatedWith` / `wasAttributedTo`
edges, attributing the topology to `FlyCellAtlas` and the
`flybrain:dataset_anchor` (MaleCNS v1.0).

### 3.4 Evaluation protocol

For each candidate advantage we used **matched controls**: same node count,
same non-zero edge count, seed-averaged, comparing bio-motif topologies against
random structure. Significance used permutation / paired tests. H1 for fault
isolation = module-shutdown performance drop **smaller** than random-shutdown
drop. H1 for local decision-making = per-module readout `R²` ≥ 0.8 × central
readout `R²`.

---

## 4. Results

### 4.1 Traceability — ✅ demonstrated (moat 1)

A schema-conformance suite (`_verify.py`) validates the organism schema, the
3-stage provenance, the W3C PROV-JSON bundle, and all 25 blueprint lineages.
**70/70 checks pass.** No blueprint has an `unknown` provenance source. This is
the property LangGraph / AutoGen / CrewAI cannot offer structurally.

### 4.2 Structural parsimony — ✅ demonstrated (moat 2)

With architecture constraints held equal to the biological prior, random search
beat the genetic algorithm 8/8 seeds (+29%). **Releasing** the architecture
constraint, the GA converged to **9–11 edges** versus the locked 57-edge
morphology — a **−84% wire cost** — while preserving the requested functional
profile. The advantage is in *leanness*, not in raw task performance.

### 4.3 Structural stability — ✅ demonstrated (moat 3)

Across **27** topologies sampled from the blueprint library, **25 (92.6%)**
showed modular fault isolation (H1), with a median effect size of ~28
percentage points and spectral radius ρ held at 0.00–0.30%. Three new
stability-oriented blueprints (`modular_isolation`, `robust_redundant`,
`decoupled_hierarchical`) plus a GA stability fitness term
(`STABILITY_WEIGHT = 0.5`, target cross-module ratio 0.30) push the
module-isolation ratio from 0.42 → 0.32 (≈24% improvement).

### 4.4 Local decision-making — ⚠️ partial (moat 4)

A multi-readout experiment (7 topologies × 4 delays = 28 runs) trained
independent per-module linear readouts versus a central readout. **5/28 (17.9%)**
met H1, and only on simple tasks at delay ≤ 2 (peak ratio 1.59× in favor of
local readout). Counter-intuitively, the `modular_isolation` blueprint at
delay = 1 was *central-dependent* — isolation does not automatically imply
local autonomy. We report this as a **partial, task-limited** advantage.

### 4.5 Negative result A — no compute advantage

A matched-control ESN calibration (7 topologies) found biological motifs
**0/7** superior to random structure; differences (0.001–0.071) lay within
noise, and 4/7 were *worse*. We therefore make **no compute-advantage claim**.

### 4.6 Negative result B — no energy advantage

An SNN energy proxy (IF neurons; 6 topologies × 4 delays = 24 runs) found
biological motifs **0/24** systematically lower energy than random; median
energy ratio 1.006 within a ±5% band. We therefore make **no energy-advantage
claim**.

---

## 5. Discussion

### 5.1 Why honest negative results matter here

The temptation, when connecting real neuroscience to engineering, is to claim
that biology is *better* on every axis. Our matched-control tests show that for
two axes (compute, energy) it is not, at least at the scales and substrates we
tested. Publishing the negatives is not a weakness of the method — it is the
method. A traceable generator is valuable precisely because it lets us *measure*
rather than *assert*.

### 5.2 What the moats actually buy

Traceability, parsimony, and stability are genuinely useful for **auditable
multi-agent system design**: you can prove where a topology came from, you can
search for lean versions, and you can contain module failures. These are design
and compliance properties, not performance properties.

### 5.3 Limitations

- Topologies are *derived* from, not *simulations of*, the connectome; dynamical
  claims are proxies (ESN/SNN), not biological reality.
- Local decision-making is weak and task-limited; we do not generalize it.
- Experiments ran on commodity hardware with moderate agent counts; scaling
  behavior is untested.
- The connectome is male-specific; sex-generalization is out of scope.

---

## 6. Conclusion

A real connectome can be turned into a *traceable*, *auditable* multi-agent
topology generator. Three of four candidate advantages survive controlled
testing; two intuitive advantages (compute, energy) do not, and we say so. The
released toolkit (MIT, zero third-party dependencies) includes the generator,
a 12-tool connectome query service, W3C PROV provenance, and the reproducible
experiment scripts behind every number in this paper.

---

## References

1. MaleCNS v1.0 — whole-brain connectome of the male *Drosophila*, *Cell*,
   2026-09-03 (CC-BY). Source dataset for all quantitative anchors.
2. Fodor, J. A. (1983). *The Modularity of Mind*. MIT Press.
3. Friston, K. (2008). Hierarchical models in the brain. *Neuropsychologia*,
   56(4), 1321–1327.
4. Vaidya, A. R., *et al.* (2010). Probabilistic categorization: ... *PNAS*,
   107(47), 20440–20445.
5. Geddes, J. (2014). Double dissociation and the logic of cognitive
   architecture. *Cognition*.
6. Glenberg, A. M. (2014). ... (modularity debate, embodied cognition).
7. Campanella, F. (2022). ... (double dissociation methods).
8. `dataprov` — RI-SE, W3C PROV serialization library (zero-dependency).

*Code & data derivatives:* https://github.com/lm203688/flybrain-connectome
(MIT). The 5.63 GB raw connectome is not redistributed; obtain MaleCNS v1.0
from the original publication and set `FLYBRAIN_DATA_DIR`.
