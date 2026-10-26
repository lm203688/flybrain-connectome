# Xu 2026 Dendritic Computation — EPE Pattern Mapping

**Document**: `docs/XU2026_DENDRITIC_PATTERN_MAPPING.md`
**Version**: v1.0 · 2026-10-25
**Purpose**: One-page mapping of Xu 2026 *Science* paper's two-compartment
dendrite/soma model onto EPE L1/L2/L4 layers and the reference code pattern.
**Scope**: Reference documentation only. Does NOT alter project architecture.

---

## 1. Xu 2026 in one paragraph

Xu Ninglong team (CAS-IBIC, published *Science* 2026-10-16,
DOI: 10.1126/science.adz5323) demonstrated with optogenetic causal evidence
that in mouse auditory cortex L5 pyramidal neurons, the **apical dendrite**
encodes inferred abstract rules, the **cell body (soma)** represents sensory
information, and the two compartments combine via a nonlinear gate to produce
behavioral decision output. Silencing the dendrite via optogenetics weakens
the soma's decision signal, providing causal evidence that dendritic
computation is *necessary* (not just correlated) for flexible decision-making.

---

## 2. One-page mapping to EPE

```
┌─────────────────────────────────────────────────────────────┐
│ Xu 2026 neuron                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│       ┌──────────────────────────┐                          │
│       │  Apical dendrite         │ ← 顶端树突                │
│       │  encodes abstract rules  │   编码抽象规则            │
│       └──────────┬───────────────┘                          │
│                  │                                          │
│                  │ nonlinear gate                           │
│                  ▼  (sigmoid of rule confidence)            │
│       ┌──────────────────────────┐                          │
│       │  Soma                    │ ← 胞体                    │
│       │  processes sensory input │   处理感觉输入            │
│       └──────────┬───────────────┘                          │
│                  │                                          │
│                  ▼ decision                                 │
│       ┌──────────────────────────┐                          │
│       │  Axon output             │ ← 轴突输出                │
│       └──────────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Cross-layer isomorphism

| Xu 2026 concept | EPE layer | flybrain-connectome object |
|---|---|---|
| Abstract rule (顶端树突) | **L1 propositional** | `Rule` in `dendritic_rule_engine.py`; upstream: motifs in `module_registry.json` |
| Sensory stream (胞体) | **L2 measurement** | `SensoryStream` encoder; upstream: connectome edge weights |
| Nonlinear integration | **L2→L4 bridge** | `NonlinearIntegrator.decide()`; upstream: `metric_family_versions.json` |
| Decision output (axone) | **L4 progress signal** | `DendriticAgent.observe()` return value; upstream: prereg verdict |
| Confidence-gated consolidation | **L2 verifiable structure** | `Rule.confidence` (Wilson lower bound); upstream: S6/S7/S8/S9 disciplines |
| Optogenetic silencing (silent-component test) | **L3 prereg verdict** | PR-2b `_f4b_metric_substitution` (analytic) vs Xu (biological) — same causal template |

### 2.2 What maps cleanly vs what does NOT

**Maps cleanly (structural isomorphism)**:
- Silent-component → measured-output test template
- Confidence-gated consolidation (few-shot support before promotion)
- Multiplicative nonlinearity between abstract and concrete signals

**Does NOT map (level-mismatch)**:
- Neuromorphic implementation — Xu is *in vivo* calcium dynamics; project has no
  subcellular representation (116 neuron-level units).
- Cross-species transfer — Xu is mouse auditory cortex; project substrate is
  Drosophila MaleCNS. Independent experimental work required.
- Combina... algebra — Xu gives an *intra-neuronal* pattern, not a new
  neuronal type. Introducing compartments into the core would break the
  combinatorial semantics.

---

## 3. Reference code objects

Located in `tools/dendritic_rule_engine.py`:

| Code object | Xu 2026 analogue | Semantics |
|---|---|---|
| `Rule` (dataclass) | One candidate rule cached in apical dendrite | Stores predictor + support/failure counts + Wilson confidence |
| `RuleCache` (class) | The apical dendrite | Holds multiple candidates, updates confidence on labelled observations |
| `SensoryStream` (class) | The soma | Encodes raw input to feature vector (identity by default) |
| `NonlinearIntegrator` (class) | Multiplicative dendrite × soma gate | Sigmoid-gated weighted vote → label |
| `DendriticAgent` (facade) | Whole pyramidal neuron (dendrite + soma + axon) | Entry point for callers wanting the pattern wrapped |

---

## 4. When to use this pattern in your own code

Use `dendritic_rule_engine.py` when:
- You want to prototype a **few-shot hypothesis generator** in an agent
  pipeline and Xu 2026's "cache rules → verify → consolidate" cycle is a
  better shape than a full LLM inference call.
- You need an **auditable alternative** to a black-box classifier: the rules
  are named, confidence-gated, and inspectable after each observation.

Do NOT use it when:
- You need real neuroscience-grade dendritic dynamics (calcium spines,
  voltage-dependent AMPAR plasticity, etc.). Xu 2026 shows these matter;
  our sigmoid gate is a *qualitative* stand-in.
- You want to introduce subcellular compartments into the flybrain-connectome
  core. That is a major architectural change (see B-14 boundary in
  `docs/E4_BOUNDARY_ATLAS.md` and §2.3 of the impact memo).

---

## 5. Cross-references

- Impact memo: `docs/XU2026_DENDRITIC_COMPUTATION_IMPACT_2026-10-18.md`
- Boundary atlas B-14: `docs/E4_BOUNDARY_ATLAS.md`
- P-4 methodological neighbour section: `docs/PAPER_P4_CASE_STUDY.md` §6.7
- EPE vision: `docs/NEXT_STAGE_VISION_EPE_2026-10-16_v0.4_ADDENDUM.md` §3
- Reference implementation: `tools/dendritic_rule_engine.py`
- Reference notebook: `examples/07_dendritic_rule_cache_demo.ipynb`

---

**Status**: Reference documentation only. flybrain-connectome core (neuron-level
combinatorial algebra) unchanged. Gate count unchanged (62). Version
bumped to 3.00.3 for discoverability.
