# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The **schema version** is versioned separately from the **package version**:

| | value | meaning |
|---|---|---|
| package | `1.6.0` | the toolkit as a whole |
| schema (organism / swarm config) | `1.2.1` | top-level generated-document shape |
| schema (`motif_provenance` block) | `1.2.0` | provenance sub-document; unchanged since v1.2.0 |
| combinator rules schema | `1.1` | 12 combination + 7 nesting + 4 multiplier semantics |
| functional-unit library schema | `1.0` | 72 units + 66 connection types (1.4.0; grown in 1.5.0 and 1.6.0) |
| fingerprint signing | `sha256` / `hmac-sha256` | unsigned local-dev / keyed service-side |

---

## [1.6.0] — 2026-09-23

**Rhythm, state and error: the library gains an oscillating and a teaching tier.**

v1.5.0 covered clades; it did not cover *time*. Every unit added there was a
feedforward or feedback computation. This release adds the three things a
composition library needs before it can express an animal that keeps going on its
own: autonomous rhythm without a cortex, a state machine that cannot sit halfway,
and one supervised error-teaching path. 24 neuron populations, 16 functional
units, 8 connection forms and 18 port types.

### Added

- **24 neuron populations** in `synthetic_bio_topology.MODULE_PROFILES`
  (136 → **160** profiles, 126 → **150** cross-species neuron types):
  segmental/peripheral oscillators 9 — leech swim-CPG interneuron, leech body-wall
  motor neuron, leech mechanosensory (T) cell, ascidian larval motor neuron,
  ascidian ocellus photoreceptor, Aplysia sensory neuron, Aplysia motor neuron,
  Aplysia serotonergic facilitating interneuron, buccal-ganglion CPG neuron ·
  infrared and amphibian 5 — trigeminal infrared afferent, infrared tectal map
  neuron, multimodal optic-tectum neuron, tectal T5-type prey detector, tongue
  motor neuron · error teaching and state 6 — climbing fibre, cerebellar Golgi
  cell, vestibular nucleus neuron, pre-Bötzinger complex neuron, phrenic motor
  neuron, VLPO neuron · navigation and active sensing 4 — head-direction cell,
  place cell, barrel cortex neuron, whisker motor neuron.
  `MODULE_REGISTRY` grows 145 → **169** in step (all 160 profiles covered).

- **16 functional units** (56 → **72**) across five new animals and three new
  computational roles: leech swim rhythm and ascidian larval escape swim (half-centre
  oscillation, no intrinsically rhythmic cell), Aplysia gill-withdrawal reflex
  (sensitisation *and* habituation on the same synapse) and buccal feeding rhythm,
  pit-viper infrared thermal map and cross-modal strike, frog tectal prey capture
  and reticulospinal escape swim, cerebellar climbing-fibre teaching and Purkinje
  LTD microzone, vestibulo-ocular reflex adaptation, respiratory rhythm
  (pre-Bötzinger), sleep/wake flip-flop, locus-coeruleus arousal broadcast,
  hippocampal spatial map, barrel-cortex active touch. Systems covered 23 → **36**.

- **8 connection forms** (58 → **66**), each with a named primary reference:
  `half_center_oscillation`, `plateau_potential_bistability`,
  `serotonergic_presynaptic_facilitation`, `short_term_habituation`,
  `coincidence_detection`, `state_switch_bistable`, `grid_phase_precession`,
  `thermal_cross_modal_convergence`.

- **18 port types** (54 → **72**): infrared, vibrissa, thermal vector, place code,
  swim / feeding / respiration / eye / strike / whisk / gill motor, swim and
  respiratory rhythm phase, sleep pressure and wake drive, hunger gate,
  climbing-fibre teaching, tactile reafference.

- **A fourth canonical demo chain**, `demo_swim_rhythm_chain` (leech half-centre
  CPG entrains the ascidian larval oscillator, which gates the frog reticulospinal
  escape swim), validated by Gate 9 every run.
  `functional_units.py --demo mammal|insect|electrosensory|swim|all`.

### Changed

- Gate 9 counts move to 72 / 66, the anatomical-system floor rises 20 → **34**,
  the distinct-population floor 110 → **140**, and the gate gained two assertions:
  every v1.6.0 connection form must be wired by a unit or a chain, and all twelve
  v1.6.0 systems must be represented. **Twelve** fail-closed injections now
  (two added: the rhythm chain wired through a non-existent out-port, and the
  rhythm chain validated in strict interior-sub-chain mode).
- The four new assertions were each proved to go red by defect injection before
  being committed (unwrap a v1.6.0 form; rename a v1.6.0 system; collapse member
  references; collapse systems onto one).

### Honest boundary

The 24 neuron types and all 16 units are **curated literature summaries**
(`provenance.extracted_from_malecns = false`), not connectome-extracted. The
oscillators are reduced to their *mechanism* (reciprocal inhibition plus
adaptation, plateau bistability) and the port-typed interface; no unit claims to
reproduce measured membrane kinetics, and none of the rhythm claims is a claim
about this project's own performance — the SNN/ESN negative results stand.

---

## [1.5.0] — 2026-09-23

**Cross-clade coverage: the library stops being mammal-cortex shaped.**

The point of this library is combinatorial coverage of the animal kingdom, not of
one brain. Four clades carry computational roles that have no vertebrate-cortex
equivalent, and if they are missing then "compose a virtual organism" silently
means "compose a mammal". This release adds them: **insect, bird, fish and
cephalopod** — 35 neuron populations, 16 functional units, 8 connection forms
and 18 port types.

### Added

- **35 cross-clade neuron populations** in
  `synthetic_bio_topology.MODULE_PROFILES` (91 → **126** neuron types, 101 → **136**
  profiles): insect 14 (Kenyon cell, MBON, PPL1/PAM dopaminergic, APL, antennal-lobe
  projection/local neurons, protocerebral bridge, ellipsoid body, fan-shaped body,
  noduli, ring neuron, s-LNv, lateral clock neuron, descending neuron) · bird 6
  (HVC, RA, LMAN, Area X, DLM, NIf) · fish 8 (Mauthner cell, reticulospinal neuron,
  lateral-line hair cell, ampullary and tuberous electroreceptors, ELL pyramidal
  cell, electrosensory inhibitory interneuron, pacemaker nucleus neuron) ·
  cephalopod 7 (vertical-lobe large/amacrine/small cells, superior frontal lobe cell,
  chromatophore motor neuron, arm motor neuron, arm sensory afferent).
  `MODULE_REGISTRY` grows 110 → **145** in step.

- **16 cross-clade functional units** (40 → **56**): mushroom-body sparse coding and
  associative memory, antennal-lobe glomerular processing, central-complex heading
  (ring attractor) and steering, insect clock pacemaker, birdsong HVC timing / RA
  motor / basal-ganglia learning loop, Mauthner escape command, passive and active
  electroreception, electric-organ-discharge pacemaker, cephalopod vertical-lobe
  learning, chromatophore control, arm motor. Systems covered 13 → **23**.

- **8 connection forms** (50 → **58**), all with a named primary reference:
  `sparse_expansion_projection`, `global_inhibitory_gain_control`,
  `neural_chain_sequence`, `efference_copy_cancellation`,
  `mixed_electrical_chemical_synapse`, `modulatory_gated_plasticity`,
  `repetitive_activation_lts`, `command_neuron_recruitment`.

- **18 port types** (36 → **54**): skylight compass, ampullary/tuberous electric,
  lateral line, startle auditory, sparse odour code, learned olfactory valence,
  heading / steering / ego-speed, clock phase, associative memory, song / escape /
  chromatophore / arm / EOD motor, efference copy.

- **Two more canonical demo chains**, both validated by Gate 9 every run:
  `demo_insect_olfactory_navigation` (antennal lobe → sparse code → learned valence →
  central complex heading/steering, clock-biased, with an intentional heading↔steering
  loop) and `demo_electrosensory_escape` (EOD pacemaker → efference-copy cancellation
  → electrolocation, plus a passive-electric cue into the escape command).
  `functional_units.py --demo mammal|insect|electrosensory|all`.

### Changed

- Gate 9 grew from 7 to **10 fail-closed injections** (efference-copy form fed by a
  non-efference source; cross-clade chain through a non-existent out-port;
  cross-clade chain validated in strict interior-sub-chain mode), and now asserts
  clade coverage, that every v1.4.1 form is actually wired by a unit or a demo
  chain, and that all three demo chains compose deterministically.
- `ephaptic_coupling` span corrected `intra_unit` → `either`: a field does not
  respect a unit boundary, and the electric organ drives its own receptors with it.
- Connection-library `source` string is now computed from the data instead of
  restating a stale "40 forms + 10 new".

### Honest boundary

The 35 new neuron types and all 16 new units are **curated literature summaries**
(`provenance.extracted_from_malecns = false`), not connectome-extracted, and not a
claim that the clade list is exhaustive. Allen's mouse atlas alone has 5,322 cell
types; this library is a deliberately conservative compositional scaffold. Insect,
bird, fish and cephalopod are represented by their *most computationally
distinctive* circuits, not by complete inventories.

---

## [1.4.0] — 2026-09-23

**The unit of composition is now a FUNCTION, not a neuron type.**

Until now the library's smallest atom was a neuron type (101 of them). That was
the wrong unit: `pyramidal_l5` alone does nothing, and wiring two neuron types
together means nothing. What composes is a function with a known interface. This
release adds the layer above the vocabulary — **40 functional units** (one
function each, delivered by a *group* of neuron populations wired into a
sub-circuit) and **50 connection types** (connection *forms*, constrained on port
types) — plus the composer that joins them and refuses malformed wiring.

### Added

- **`flybrain-connectome-mcp/functional_units/functional_units.json`** — 40
  functional units. Each declares `members` (role → neuron population from the
  101-module vocabulary, with composition ratios), `internal_wiring` (edges typed
  by connection form), and typed `ports` (`in` / `out`, with `required` flags).
  Coverage: 13 anatomical systems, 87 of 101 neuron populations, retina →
  thalamus → cortex → basal ganglia → cerebellum → motor → neuromodulatory →
  glia.
- **`flybrain-connectome-mcp/functional_units/connection_types.json`** — 50
  connection forms in six families: `micro` (10 point-to-point contact sites),
  `circuit` (15 multi-neuron motifs), `modulatory` (6), `electrical` (5,
  incl. glial coupling), `plasticity` (5), `macro` (9 population-level
  projection geometries). 40 of them map 1:1 onto the existing motif document;
  10 macro forms (divergent fan-out, convergent fan-in, corollary discharge,
  global broadcast, …) are new. Each carries `from_port` / `to_port`
  constraints, sign, fan-out, delay class and a literature reference.
- **`flybrain-connectome-mcp/functional_units.py`** — the composition engine
  (stdlib only). `compose_from_units()` enforces port-type compatibility,
  required-port satisfaction, whole-organism drivability/readability, and reports
  feedback cycles. Boundary semantics: an unsatisfied *required* input on the
  organism boundary IS the organism's external input (pass
  `allow_boundary_inputs=False` to validate an interior sub-chain). Output is
  deterministic — the input spec's sha256 is embedded.
- **`scripts/gen_functional_units.py`** — authors both artifacts. It loads
  `MODULE_PROFILES` first and **refuses to write** if any member neuron, wiring
  type, port type or `composable_with` target does not resolve, so the artifacts
  cannot drift from the vocabulary they are built on.
- **`scripts/check_functional_units.py` (Gate 9)** — proves the library cannot
  silently rot: artifacts are byte-identical to generator output (drift = fail),
  every reference resolves, composition is deterministic, and **seven injected
  defects must each be rejected** (unknown connection type, two port-type
  violations, non-existent port, unknown unit, forbidden dangling boundary input,
  empty composition). The gate itself was defect-tested: a hand-edited artifact
  and a renamed member neuron both turn it red.
- **4 MCP tools** (Tier-1, offline): `list_functional_units`,
  `get_functional_unit`, `list_connection_types`, `compose_from_units`.

### Changed

- Package version 1.3.0 → 1.4.0. Advertised tool count 40 → **44**; bare public
  install (no Tier-2 core) 36 → **40**. `core_bridge.TOTAL_TOOLS` is now the
  single source of truth for that number and Gate 8 asserts it matches
  `check_physical_tiering.TOTAL_TOOLS`, so the two cannot diverge.
- Gate 2 now also requires the new tool names and the counts in `README.md`,
  `docs/mcp_setup.md` and the registered `mcp.json` description.
- `scripts/run_gates.py` runs Gate 9 alongside the dependency-free gates (it is
  stdlib-only, so `--quick` includes it) and gate labels are renumbered without
  the misleading `/N` fragments.

### Honest boundary

The 40 units are curated from comparative-neuroscience literature with a named
reference each; `provenance.extracted_from_malecns` is **`false` for all 40** —
unlike the three original fly motifs, they are not extracted from MaleCNS v1.0.
Member ratios are composition weights, not measured cell counts. The layer is a
composable scaffold with literature provenance, not a measured cell assembly.

---

## [1.3.0] — 2026-09-22

**Physical tiering executed — Tier-2 IP is now absent from the public tree.**

Closes the gap left by v1.2.2: the tiering *mechanism* existed, but every Tier-2
artifact still physically shipped in the MIT repo (all rule tables, data artifacts,
and discovery pipelines were MIT-licensed in practice). The public tree is now
genuinely clean — a bare `pip install` exposes 36 of the 40 MCP tools, the combinator
is a 5.5 KB seam carrying no rule payload, and Gate 8 fails the build if any Tier-2
content reappears.

### Added

- **`scripts/push_core.py`** — manifest-driven Tier-2 mover with `--verify` / `--push`
  / `--delete --yes`, driven by `core_bridge.TIER2_ARTIFACTS` as the single source of
  truth. Content resolves from the local tree, falling back to the outside-repo backup
  for the stubbed seam (the local copy of `module_combinator.py` is the public stub,
  not the IP).
- **`scripts/check_physical_tiering.py` (Gate 8)** — asserts the license declaration,
  the degradation + tool-count contract (40 − 4 = 36 bare), **physical absence** of
  every Tier-2 payload, and that the private repo actually holds 15/15 artifacts.
- **Thin combinator seam** — `module_combinator.py` 29.3 KB → 5.5 KB. The same 10
  public functions and `SCHEMA_VERSION = "1.1"` survive; every rule lookup delegates to
  `flybrain_core.module_combinator` or returns a `tier2_required` envelope that names
  the tool and carries no payload.

### Changed

- Package version 1.2.2 → 1.3.0 (feature: enforced physical isolation + new gate).
- `core_bridge.CORE_DEPENDENT_TOOLS` corrected 9 → **4**. The earlier figure counted
  `list_neuropils` / `get_neuropil_detail` and the `MODULE_PROFILES` readers as
  Tier-2-dependent; they read Tier-1 data (`neuropil_stats.json`, inline profiles) and
  work bare. Functional tool count is **36**, not 31.
- `LICENSE-CLAUSE.md` rewritten to match reality: Tier 1 no longer claims the discovery
  scripts or the full combinator are open; the Tier-2 table lists the 14 relocated
  artifacts; the stale "9 tools" claim is replaced with 4.
- `scripts/fingerprint_organism.py` confirmed **Tier 1** and stays public (format +
  generic key loader only; no proprietary data). Only the signing *key* is Tier 3.

### Security

- **14 Tier-2 artifacts deleted** from the public repo and the working tree: 6 data
  JSONs, 7 `scripts/module_discovery/` files, and `scripts/data_driven_rules.py`.
  Empty `scripts/module_discovery/` pruned.
- **Private repo** `lm203688/flybrain-connectome-core` holds **15/15** artifacts,
  including the 29.3 KB real combinator, plus a Tier-2 `README.md` and
  `LICENSE-CLAUSE.md`.
- Local backup retained **outside** the repo at
  `C:/Users/xing/Desktop/flybrain-tier2-backup-2026-09-22` with
  `MANIFEST.sha256.json` (15/15 round-trip verified).

### Security — visibility change (2026-09-22)

- **Repo made private.** `PATCH /repos/lm203688/flybrain-connectome {"private":true}`
  succeeded; anonymous access to the API, contents, and
  `raw.githubusercontent.com` all return 404. This immediately stops public exposure
  of the Tier-2 files that remain in git history.
- **README and LICENSE-CLAUSE updated** to note the private status and the
  re-publicization plan.
- **Gate 8 unaffected** — it only asserts the *private* repo's visibility, not the
  main repo's.

### Known residual

- The 14 Tier-2 files deleted at HEAD are **still reachable in git history** from
  v1.2.0 / v1.2.1. They are now **no longer publicly accessible** (repo is private),
  but a full scrub requires a history rewrite + force-push, which needs a machine with
  direct `github.com:443` access (the Contents-API push channel cannot rewrite history,
  and local `git push` is blocked from this network). The canonical protected copy is
  the private repo `lm203688/flybrain-connectome-core`.

---

## [1.2.2] — 2026-09-21

**Physical tiering mechanism + HMAC anti-forgery + data-driven rule discovery + task-level multiplier redefinition.**

### Added
- **HMAC-SHA-256 fingerprint signing** (`scripts/fingerprint_organism.py`): service-side
  keyed signatures make organism fingerprints unforgeable without the server key;
  SHA-256 remains the unsigned local-dev fallback. New Gate 7 §4b enforces it.
- **Data-driven combination-rule discovery** (`scripts/data_driven_rules.py`): derives
  candidate rules directly from the real 27×27 connectome matrix via an independence
  null model (enrichment + z-score). Output `male_cns/candidate_combination_rules.json`.
  `module_combinator.audit_rules_against_data()` reconciles the 12 curated rules
  against the evidence (e.g. `ol_sensory→ol_intrinsic` enrichment 2.76,
  `visual_projection→visual_centrifugal` 3.38 are data-supported).
- **Physical tiering bridge** (`flybrain-connectome-mcp/core_bridge.py`) + **Gate 8**:
  public code prefers the private Tier-2 package `flybrain_core`; bare public install
  degrades to 31 functional tools (40 − 9 Tier-2-dependent). (Irreversible IP removal
  from the public git tree is staged separately, pending explicit push confirmation —
  the files are also in git history from v1.2.0/1.2.1.)
- **Performance multiplier redefined to task-level** (`scripts/performance_multiplier_tasklevel.py`):
  A/B/C three-arm framework (organism prior vs random vs none) measuring task success
  rate / relative latency / structural traceability — replaces the engine-level metric
  that was negative (SNN 0/24, ESN 0/7).

### Changed
- Package version 1.2.1 → 1.2.2; combinator schema v1.1 unchanged.
- `MULTIPLIER_SEMANTICS["performance"]` now honestly states `measured=False` and points
  to the task-level framework instead of any engine-speed claim.

---

## [1.2.1] — 2026-09-21

**Layer-2 combinator expansion + Tier-2 physical separation.**

Triggered by Kaganovsky / Pașca et al. *Nature* 2026 (DOI
`10.1038/s41586-026-11032-2`) — human cortical organoids implanted into
apallial mice integrate to 91.9% cortical volume yet mice still behave as
mice — direct empirical support for the connectome-determinism thesis
underpinning Layer-2 combination rules.

### Added

- **5 new paper-anchored combination rules** (`module_combinator.py`,
  schema v1.1):
  - `state_gated_combination` — state-gated activation windows
    (Beiran & Litwin-Kumar 2025, Quian Quiroga 2020)
  - `inhibitory_balance_gate` — E/I balance range [0.3, 3.0]
    (Khona & Fiete 2022, Dorkenwald et al. 2024)
  - `hub_integration` — rich-club hub broadcast (Dorkenwald 2024: 30%
    fraction)
  - `hierarchical_attractor_encapsulation` — reusable attractor units
    (Khona & Fiete 2022)
  - `homolog_role_alignment` — cross-species wiring-role binding
    (Throesch 2024, Pașca 2026, Özel & Desplan 2025)
- **3 new nesting rules**: `inhibitory_wrap`, `attractor_encapsulation`,
  `cross_species_role_binding`
- **1 new multiplier semantic**: `cross_species_invariance` — 5/7
  conserved across fruit fly + worm (71.4%)
- **Rule-specificity ranking**: `_specificity()` + `find_all_rules()` for
  handling double-wildcard constraint rules alongside specific rules
- **`docs/connectome_determinism_papers.md`** — 17-paper literature
  survey anchoring the new rules

### Changed

- **Physical tier-2 separation**: `lm203688/flybrain-connectome-core`
  (private repo) now hosts the full IP — MODULE_PROFILES,
  COMBINATION_RULES / NESTING_RULES / MULTIPLIER_SEMANTICS, all
  module-discovery scripts + clustering parameters, all data artifacts
  (`discovered_modules*.json`, `worm_modules.json`, `superclass_matrix.json`),
  and HMAC signing. The public repo retains functional MIT code but the
  proprietary rule tables live in the private repo.

### Verified

- Gate 7 updated to accept `MULTIPLIER_SEMANTICS` with ≥3 keys
- All 6 gates PASS on 1.2.1
- Layer-2 self-test: 5 combos + 3 nesting chains all validate

### Honest boundary

- Neuropil × Superclass cross-tab requires per-body neuropil membership,
  which is not in the source data (`body_annotations.somaLocation` is a
  body-id array, not a neuropil name). Deferred — see
  `.workbuddy/memory/MEMORY.md`.

## [1.2.0] — 2026-09-21

Data-driven module architecture v2: neuropil-grain module discovery,
cross-species (C. elegans) lower-bound validation, standardized
combination middleware, and three-tier anti-plagiarism enforcement.
Tool count **36 → 40**. Gate count **6 → 7**.

### Added

- **Neuropil-grain module discovery** (`male_cns/discovered_modules_neuropil.json`)
  — descends the existing superclass (27) analysis to neuropil (146) grain.
  Merges left/right pairs (146 → 81), clusters on NT(7) + log(synapses) +
  log(density) via Ward hierarchical clustering, cross-validated by Louvain
  (Q=0.4704, better than superclass's Q=0.3748). Produces 10 functional
  units with 100% coverage; 5 cholinergic, 3 histaminergic, 2 dopaminergic.
  - New script: `scripts/module_discovery/step1b_neuropil_cluster.py`

- **Cross-species lower-bound validation** (`data/worm/worm_modules.json`)
  — fetches Cook et al. 2019 C. elegans hermaphrodite connectome
  (302 neurons, 3,671 chemical + 1,090 gap edges) from the
  Netzschleuder mirror of Emmons Lab data. Runs the same Ward + Louvain
  pipeline at neuron-node grain, produces 12 units with Q=0.5173.
  - New script: `scripts/module_discovery/step1c_worm_modules.py`
  - Explicit cross-species comparison: `sensory → inter → motor` is the
    conserved skeleton; fruit-fly-specific recurrent memory cores
    (81%/88% self-loop) do NOT exist in worm at 302 scale — confirming
    recurrent memory is a large-brain structural inevitability, not a
    universal module.

- **Module Combinator Middleware** (`flybrain-connectome-mcp/module_combinator.py`)
  — standardizes layer-2 combination rules with three rule types:
  1. **CombinationRules** (7 rules) — allowed cross-category connections,
     data-driven from `cross_superclass_top` in discovered_modules.json
  2. **NestingRules** (4 rules) — module multi-copy, hierarchical containment,
     modulation wraps-any, no-self-containment
  3. **MultiplierSemantics** (3 semantics) — combinatorial (C(19,4)=4032),
     structural (fault isolation 25/27), performance (**⚠️ unverified**)
  - New MCP tools: `list_combination_rules`, `validate_combination`,
    `expand_organism`, `get_multiplier_metrics`

- **Anti-plagiarism three-tier enforcement** (`LICENSE-CLAUSE.md` +
  `scripts/fingerprint_organism.py`):
  - **Tier 1 — Open (MIT)**: interfaces, schemas, documentation
  - **Tier 2 — Closed (Proprietary)**: derived payloads (raw .npy/.feather,
    worm zips, generated organisms)
  - **Tier 3 — Service-side (API-key)**: SHA-256 fingerprints per organism,
    embedded on save; every save_market_organism call now computes
    `flybrain:organism-v1:<sha256>` fingerprint and stores it in the entry

- **Gate 7: module architecture integrity** (`scripts/check_module_architecture.py`)
  — 32 checks across neuropil modules, worm data, combinator middleware,
  fingerprint determinism, LICENSE-CLAUSE content, and MCP tool registration.

### Changed

- **Version bumped** to 1.2.0 across `pyproject.toml`, `server.py`,
  `api_server.py`, `__init__.py`, `flybrain_cli.py`, `CITATION.cff`.
- **`.gitignore` extended** with Tier 2/3 entries:
  `data/worm/raw/*.zip`, `male_cns/virtual_organisms/organism_*.json`,
  `male_cns/generated_organisms/`, `flybrain-connectome-mcp/module_combinator.cache/`.

### Notable data points

- Neuropil grain: 146 raw → 81 merged → 10 Ward clusters, coverage 100%
- Worm grain: 302 neurons → 12 clusters, Louvain Q=0.5173
- Fly Louvain Q=0.4704 (neuropil) > 0.3748 (superclass) — finer grain
  reveals more structure
- Worm Louvain Q=0.5173 > fly's 0.4704 — smaller, sparser graph has more
  community structure (expected)
- 7 combination rules + 4 nesting rules + 3 multiplier semantics
- Performance multiplier remains 0/24 SNN + 0/7 ESN (unverified, per
  project hard constraint)

---

## [1.1.0] — 2026-09-20

Module factory v2: variant true differentiation, SwarmLabs agent-team
integration, and a virtual-organism market. Tool count **28 → 36**.

### Added

- **Variant true differentiation** — module variants (e.g. `sensory_vision`,
  `sensory_sound`, `sensory_touch`) now carry real parameter overrides
  (`reservoir_density`, `recurrent_pct`, `has_inhibition`) injected into
  `MODULE_PROFILES`. Variants produce measurably different topologies, not
  just cosmetic labels. Blueprint prefix-matching (`sensory_*` → `sensory`)
  ensures variant profiles participate in cross-module wiring.
- **SwarmLabs agent-team integration** (`organism_to_swarmlabs`,
  `get_module_agent_roles`) — converts any generated organism into a SwarmLabs
  multi-agent team spec (agents, modules, edges, guardrails, validation,
  motif_provenance, prov_json). 19 modules mapped to Agent roles.
- **Virtual-organism market** (`save_market_organism`, `load_market_organism`,
  `list_market_organisms`, `rate_market_organism`, `search_market_organisms`,
  `delete_market_organism`) — local file-based CRUD for sharing custom module
  combinations, with tag filtering, rating (1-5), and keyword search.
- **Cycle detection softening** — biological recurrent/predictive/reward loops
  no longer trigger hard conflicts in `check_module_compatibility`; only cycles
  involving 3+ distinct modules are flagged.
- **Module factory v2** — 19 modules, 10 presets, nested composition
  `a+(b+c)`, variant overrides, blueprint stacking.

### Fixed

- **Blueprint prefix matching** — `_apply_blueprint()` now matches variant
  profiles (`sensory_vision`) to base blueprint rules (`sensory`) via
  `startswith` prefix check, and flattens list-of-lists with `extend`.
- **Variant profile field copies** — `capability` and `task_hint_pool` now
  use `list()` to avoid mutable-reference hash errors.

### Tool count

28 (v1.0.0) → **36** (v1.1.0). New tools: `organism_to_swarmlabs`,
`get_module_agent_roles`, `save_market_organism`, `load_market_organism`,
`list_market_organisms`, `rate_market_organism`, `search_market_organisms`,
`delete_market_organism`.

---

## [1.0.0] — 2026-09-19

First public release. MIT licensed, standard-library only, zero **required**
third-party dependencies. (`dataprov`, which serializes the W3C PROV-JSON
bundle, is an optional extra — `pip install "flybrain-connectome[prov]"`. Without
it the toolkit runs and still records structural provenance; see the defects
found by the first CI run below.)

### Added

- **Connectome query service** — 21 tools over HTTP (`:8799`) and MCP stdio,
  backed by the real MaleCNS v1.0 dataset (166,700 neurons / 124,177,617
  synapses / CC-BY). 11 tools query the connectome (`export_swarm_motifs` also
  works offline, reading the bundled snapshot); 5 expose the generator surface
  (`list_blueprints`, `list_modules`, `list_bio_motifs`,
  `batch_generate_topologies`, `get_provenance_bundle`).
- **Unified developer CLI** (`flybrain_cli.py`, `flybrain` console script) with
  `serve` / `query` / `motifs` / `generate` / `verify` / `info`.
- **Synthetic bio-topology generator** (C1) — composes task-tailored agent
  graphs from 25 blueprints over 10 functional modules. Runs fully offline from
  a 7 KB derived motif snapshot; the 5.63 GB connectome is only needed to
  *query* the real brain.
- **W3C PROV-JSON provenance** (schema v1.2.1) — every generated artifact carries
  a `prov_json` bundle with `entity` / `activity` / `agent` nodes and
  `wasDerivedFrom` / `wasAssociatedWith` / `wasAttributedTo` edges, attributing
  each topology to `FlyCellAtlas` and a `flybrain:dataset_anchor`. Consumable by
  yProv4ML, MLflow2PROV and MIT Sloan provenance tooling.
- **Three-stage motif traceability** — neuron anchor (stage 1) → synapse-class
  statistics as a share of the 124M-synapse dataset (stage 2) → runnable
  query (stage 3).
- **Reproducible diagnostics** in `integrations/swarmlabs/diagnostics/`:
  `fault_isolation_experiment.py`, `snn_energy_experiment.py`,
  `multi_readout_experiment.py`, `cell_densify_experiment.py`,
  `dyn_calibration_probe.py`, plus the GA search in `ga_evolve_topology.py`.
- **Gates** — `flybrain verify` (`_verify.py`, 70/70), `scripts/check_mcp_tools.py`
  (every advertised MCP tool must actually respond),
  `scripts/check_docs_consistency.py` (docs must not drift from code).
- `CITATION.cff`, `docs/arxiv_paper.md`, `docs/mcp_setup.md`.

### Measured claims

Three hold up under matched-random controls; two did **not**, and are reported
as negative results rather than dropped:

| claim | evidence | status |
|---|---|---|
| Traceability | `_verify.py` 70/70; `prov_json` on every artifact | real |
| Structural parsimony | GA converges to 9–11 edges vs 57 locked → **−84 %** wire cost | real |
| Structural stability | modular fault isolation in **25 / 27** topologies (92.6 %); spectral radius ρ within 0.00–0.30 % | real |
| Local decision-making | multi-readout **5 / 28** (17.9 %), simple / delay ≤ 2 tasks only | partial |
| Compute advantage | **0 / 7** topologies beat random structure | dropped |
| Energy advantage | **0 / 24** runs beat random (median ratio 1.006 ± 5 %) | dropped |

### Security

- **A live API key was published and has been rotated.** The service key was
  hardcoded in four files (`flybrain-connectome-mcp/README.md`,
  `integrations/swarmlabs/benchmark_module_stacking.py`,
  `e2e_bio_advantage.py`, `ga_evolve_topology.py`) and was therefore readable
  anonymously on `main` of this **public** repository. No gate existed that
  could notice. The key was rotated, every literal removed in favour of
  `$FLYBRAIN_API_KEY` / a single non-committed local source, and
  **`scripts/check_no_secrets.py`** now fails on any publishable credential
  before a push. Scope of exposure: the service binds `127.0.0.1` by default,
  so practical impact is limited to anything that had copied the key — but the
  old value must be treated as public and unusable. See the
  [rotation note](#api-key-rotation-2026-09-19) below.

### Fixed before release

Defects found by the release-acceptance pass. They are listed because each one
had passed the pre-existing gates:

- **`flybrain generate` dropped pass-through flags.** `argparse.REMAINDER`
  inside a sub-parser no longer captures a leading `--flag` on Python ≥ 3.13,
  and mixing captured values with leftovers scrambled flag/value pairing.
  `generate` now forwards its raw argv to the generator's own CLI.
- **Five advertised MCP tools were dead.** `_load_topology_module()` referenced
  an undefined `HERE` (the real constant is `_MOTIFS_DIR`), so
  `list_blueprints`, `list_modules`, `list_bio_motifs`,
  `batch_generate_topologies` and `get_provenance_bundle` all returned
  `NameError`. `tools/list` still advertised them, and `_verify.py` stayed
  green because it never exercised the MCP handlers.
- **`list_bio_motifs` crashed** on `BLUEPRINT_SOURCE_MOTIF`, whose values are
  dicts (`{"motif", "note", "stability_target"}`) rather than strings.
- **`is_bio_prior` was always `true`.** Comparing those dicts against the
  string `"none"` could never be false, so all 25 blueprints were reported as
  bio-prior. Now 16 bio-prior / 9 not, matching the documented split.
- **`batch_generate_topologies` ignored its own contract.** The dispatcher
  passed the whole argument object where a list was expected (`TypeError:
  slice`); the published `inputSchema` advertised a `modules` array while the
  implementation required `n_modules: int`. Both sides now agree, and
  `max_nodes` is honoured (reported via `exceeds_max_nodes`).
- **Version literals could drift.** `_motif_provenance()` hardcoded `1.2.0`
  while the enclosing organism hardcoded `1.2.1`. Both now come from named
  constants, and `check_docs_consistency.py` asserts the split stays explicit.
- **A frozen Phase-3 artifact mis-declared its leader.**
  `evolved_phase3_free_…hierarchical_deep.swarm.json` (90 agents / 9 edges — the
  free GA search behind the −84 % wire-cost result) set
  `agentteams.leader = "m0_rep"`, a module-0 member, so the downstream SwarmLabs
  loader rejected it with `leader_inside_module`. The free search dropped the
  global coordinator *by construction* — that is why it reached 9 edges — so the
  truthful declaration is `leader: null`, which the loader accepts. **No topology
  and no edge metric changed** (still 90 agents / 9 edges); only the wrong
  metadata was corrected, and the file records the repair inline. Found by
  `integrations/swarmlabs/check_swarmlabs_sync.py`, which no other gate runs.

### Fixed after the first CI run

The gates above all ran on a developer machine, where `dataprov` is installed.
CI is a bare interpreter, and that difference exposed two more defects — both
of the same shape: a `dict.get(key, default)` that looks safe and is not.

- **Two advertised tools crashed without the optional dependency.** The
  generator returns `prov_json: None` — not a missing key — when `dataprov` is
  absent. `cfg.get("prov_json", {})` does not help: a default applies only to
  an *absent* key, so the value stayed `None` and
  `get_provenance_bundle` answered
  `ERROR: 'NoneType' object has no attribute 'keys'`. It now reports
  `prov_available: false`, keeps the structural `motif_provenance`, and names
  the missing package in `prov_unavailable`.
- **`batch_generate_topologies` reported failures as successes.** The same
  `None` was read as a dict inside its per-spec `try`, so a crash became a
  per-item `error` while the envelope still said `isError: false` with
  `generated: 1` and no agents or edges. The envelope now separates
  `attempted` / `succeeded` / `failed`, so partial failure is impossible to
  mistake for success. (`generated` is gone — attempts were never successes.)
- **New regression guard: `scripts/check_degraded_mode.py`.** A crash on a
  missing *optional* dependency is invisible to local testing by construction,
  so it needs its own probe. The checker runs the server twice — once with
  `dataprov` shadowed by a module that raises `ImportError`, once normally — and
  asserts that the absent arm degrades honestly *and* that the present arm
  actually produces the bundle. Without the second arm, a build that silently
  stopped emitting provenance would also pass.
- **New `scripts/check_generated_artifact.py`.** `generate` exiting 0 proves
  nothing about its output. This asserts the artifact's real invariants:
  `metrics` agree with the payload, `dangling_edges == 0`,
  `leader_is_module_member is False`, `weights_in_range is True`, and the PROV
  chain still contains `wasAssociatedWith` + `FlyCellAtlas`. Self-tested by
  injecting six mutations — all six caught, control green.

### Continuous integration

`.github/workflows/ci.yml` runs on every push and PR, in two job families:

- `gates` (Python 3.10 / 3.12 / 3.13) — `compileall`, credential gate,
  docs-drift gate, MCP tool gate (`--offline`), degraded-mode gate, CLI
  self-check, generator smoke test, artifact-invariant gate.
- `package` — `pip install ".[prov]"`, then runs the installed `flybrain`
  console script via `FLYBRAIN_HOME` and asserts the artifact it produces. This
  is the README install claim, executed rather than asserted; it also validates
  that the `prov` extra actually resolves.

`workflow_dispatch` is enabled for on-demand re-runs. GitHub's free runners
never download the 5.63 GB dataset, so the 11 data-backed tools are covered by
`flybrain verify` (70/70) on a machine that has the connectome, not in CI.

### Documentation

- README tool count corrected from 12 to **17** (the registry is the source of
  truth); all 17 tool names are now listed and machine-checked.
- Install instructions rewritten around what is actually verifiable:
  clone-and-run, or `pip install -e .`. A plain `pip install .` ships only the
  launcher and needs `FLYBRAIN_HOME` — stated explicitly instead of implied.
- `flybrain info` added so a broken install names itself instead of raising a
  bare `ImportError`.

### API key rotation (2026-09-19)

What happened, so the next person does it faster:

1. A pre-push grep for the key found it in 4 files that git would publish.
2. The repository was confirmed **public**, and `raw.githubusercontent.com`
   served one of those files **anonymously** — i.e. the key was already
   exposed, not merely at risk.
3. The key was rotated in `flybrain-connectome-mcp/mcp_connectome/config.json`
   (the authoritative local source; gitignored).
4. All four literals were replaced: shell examples use `$FLYBRAIN_API_KEY`,
   Python examples use `os.environ`, and the three experiment scripts resolve
   through the new `integrations/swarmlabs/_local_key.py`
   (`env` → local `config.json`, never a literal).
5. `scripts/check_no_secrets.py` was added and verified to **fail** on an
   injected key before being trusted.
6. The old value is dead. If you copied it, it no longer works — set
   `FLYBRAIN_API_KEY` or generate a new one:

   ```bash
   python -c "import secrets;print('flybrain_'+secrets.token_hex(32))"
   ```

**Not done, and worth knowing:** the old key remains in this repository's
*commit history* (the first push at 2026-09-19T05:42Z). HEAD is clean, and the
credential is rotated, so history rewriting was judged unnecessary — but if you
forked during that window, rotate rather than trust the value.

---

## Version history before the public release

Development ran in phases; the summaries live in `PROJECT_VISION.md` and
`HISTORY.md`, and the reproducible evidence in
`integrations/swarmlabs/*.md`.

| phase | date | outcome |
|---|---|---|
| 1 — module library 4 → 10 | 2026-09-18 | 10 functional module profiles |
| 2 — blueprint library 12 → 22 | 2026-09-18 | nested composition `a+(b+c)`; motif-traced blueprints |
| 3 — automatic topology search | 2026-09-18 | GA −84 % wire cost; **compute claim failed** (0/7 vs random) |
| 3.5 — module fault isolation | 2026-09-18 | 27-topology sample: **25/27** modular H1 |
| 4 — moat deepening | 2026-09-19 | schema v1.2.0 three-stage provenance; GA stability fitness; 22 → 25 blueprints |
| 4.2.1 — dataprov integration | 2026-09-19 | schema v1.2.1 `prov_json`; `_verify.py` 70/70 |
| 5 — untested dimensions | 2026-09-19 | **energy claim failed** (0/24); local decision-making partial (5/28) |
| 6 — release engineering | 2026-09-19 | CLI, packaging, docs, gates, this changelog |
