# Module Architecture v2 — Data-Driven & Cross-Species

This document is the authoritative description of the module-discovery pipeline
introduced in v1.2.0. It covers:

1. **Superclass grain** (27 units, v1.1.0) — the original analysis
2. **Neuropil grain** (146 → 10 units, v1.2.0) — the descent into finer anatomical structure
3. **Cross-species** (C. elegans 302 → 12 units, v1.2.0) — the lower-bound validation
4. **Combination rules** (7 rules, v1.2.0) — the layer-2 middleware
5. **Anti-plagiarism tiers** (3 tiers, v1.2.0) — the license split

All conclusions are backed by data files committed alongside this document.

## 1. The three data-driven grain levels

| Grain | Source | Units | Louvain Q | Coverage |
|-------|--------|-------|-----------|----------|
| Superclass | `superclass_matrix.json` | 8 (from 27) | 0.3748 | 99.97% synapses |
| Neuropil | `discovered_modules_neuropil.json` | 10 (from 146) | 0.4704 | 100% synapses |
| Worm neuron | `data/worm/worm_modules.json` | 12 (from 302) | 0.5173 | 100% neurons |

**Key finding**: finer grain = higher modularity Q. This means the brain has
*more* structure at the neuropil level than at the superclass level, which is
the opposite of what you'd naively expect. The neuropil grain reveals separate
functional units (e.g. dopaminergic visual system) that collapse together at
superclass.

## 2. Neuropil descent

### Pipeline

```
neuropil_stats.json (146 raw)
    ↓ merge L/R pairs
neuropil_list (81 merged)
    ↓ Ward hierarchical clustering on NT(7) + log10(synapses) + log10(density)
k=10 clusters
    ↓ Louvain on NT distance graph (cross-validation)
6 communities, Q=0.4704
```

### The 10 neuropil units

| Unit | Dominant NT | Synapses | % of total | Key neuropils |
|------|-------------|----------|------------|---------------|
| cholinergic_unit | ACh 0.56 | 229M | 73.51% | ME, LO, LegNp(T1-3), AVLP, GNG |
| cholinergic_unit_2 | ACh 0.53 | 63M | 20.25% | LH, SPS, LAL, WED, SIP |
| cholinergic_unit_3 | ACh 0.49 | 9.9M | 3.17% | VNC, FLA, PRW, CA, EB |
| dopaminergic_unit | DA 0.72 | 3.8M | 1.22% | gL, aL, b'L, bL, a'L |
| histominergic_unit | HA 0.45 | 3.4M | 1.09% | LA, Optic-unspecified |
| cholinergic_unit_4 | ACh 0.49 | 1.7M | 0.54% | PB, ATL, mVAC(T3), CAN, NO |
| histominergic_unit_2 | HA 0.31 | 377K | 0.12% | CV, MesoLN, MetaLN |
| cholinergic_unit_5 | ACh 0.51 | 244K | 0.08% | DMetaN, AME, AbNT, AB |
| cholinergic_unit_6 | ACh 0.47 | 78K | 0.03% | ADMN, PDMN, AbN4, MesoAN |
| histominergic_unit_3 | HA 0.44 | 6K | 0.00% | CRN, CvN, AbN1-3 |

**Interpretation**: The 5 cholinergic units are not the same module — they are
5 *distinct anatomical regions* that happen to share acetylcholine dominance.
ME+LO (mushroom body + lobes) form the biggest single functional cluster, while
the dopaminergic unit (visual system: gL, aL, b'L, bL, a'L) is the only
non-cholinergic unit at >1M synapses.

## 3. Cross-species: fruit fly vs C. elegans

### Worm analysis

- **Source**: Cook et al. 2019, 302 neurons, 3,671 chemical edges, 1,090 gap edges
- **Method**: neuron-node features (out_role3 + in_role3 + role_1hot3 + log_deg2)
- **Result**: 12 Ward clusters, Louvain Q=0.5173 (7 communities)

### Conserved vs species-specific

| Category | Fruit fly | Worm | Status |
|----------|-----------|------|--------|
| sensory_input | ol_sensory + cb_sensory + vnc_sensory | sensory role | ✅ conserved |
| relay | ascending + descending | inter role | ✅ conserved |
| motor_output | vnc_motor | motor role | ✅ conserved |
| **recurrent_memory** | ol/cb/vnc_intrinsic (81/88/71% self-loop) | ❌ not present | fly-specific |
| sensory_transform | visual_projection + centrifugal | ❌ not present | fly-specific |
| modulation | endocrine + efferent | ❌ not present | fly-specific |
| **pharyngeal_reflex** | ❌ not present | I1-I6 + M1-M5 + MI | worm-specific |
| **gap_junction_coupling** | negligible | 1,090 edges | worm-specific |

### The central finding

**Recurrent memory cores (81%/88% self-loop) do NOT exist in C. elegans at
302 neurons.** This is a scale-driven structural consequence: a worm has
302 neurons total, so it cannot form "enough of the same cell type" to
create a self-recurrent memory core. The recurrent memory module is thus
a **large-brain inevitability**, not a universal module.

The sensory → inter → motor funnel, by contrast, is the *universal* skeleton
present in both species.

## 4. Layer 2: Combination Rules

The `module_combinator.py` middleware defines three rule types:

### 4.1 CombinationRules (7 rules)

| Rule | From | To | Observed synapses | Probability |
|------|------|----|-------------------|-------------|
| sensory_to_recurrent | sensory_input | recurrent_memory | 200K | 0.85 |
| recurrent_to_visual | recurrent_memory | sensory_transform | 8.08M | 0.92 |
| recurrent_to_motor | recurrent_memory | motor | 1.5M | 0.78 |
| relay_bidirectional | relay | recurrent_memory | 900K | 0.65 |
| modulation_to_all | modulation | * | 300K | 0.55 |
| sensor_array_fanin | sensory_input | sensory_input | 50K | 0.40 |
| memory_self_loop | recurrent_memory | recurrent_memory | 80M | 0.82 |

Every rule is traceable to a specific superclass pair in
`discovered_modules.json` → `top_downstream`.

### 4.2 NestingRules (4 rules)

- `module_multicopy` — same module, up to 8 copies (combinatorial)
- `hierarchical_containment` — 3 allowed chains, max depth 3 (structural)
- `modulation_wraps_any` — modulation can wrap any combination
- `no_self_containment` — recurrent_memory cannot nest inside itself

### 4.3 MultiplierSemantics (3 semantics)

| Semantic | Value | Verified? | Method |
|----------|-------|-----------|--------|
| combinatorial | C(19,4) = 4,032 | ✅ | Pure combinatorics |
| structural | 25/27 (92.6%) | ✅ | 27 topologies × 12 fault scenarios |
| performance | 0/24 SNN + 0/7 ESN | ⚠️ **unverified** | Virtual vs random topology |

**⚠️ Hard constraint**: The performance multiplier is NOT verified. The engine
does not distinguish topologies by score (engine characteristic, not project
limitation). Do NOT claim performance improvements.

## 5. Anti-plagiarism tiers

See `LICENSE-CLAUSE.md` for the full text. Summary:

| Tier | Scope | License |
|------|-------|---------|
| 1 | Code interfaces, schemas, docs | MIT |
| 2 | Derived payloads (.npy, .feather, worm zips) | Proprietary |
| 3 | Service-side signed fingerprints | API-key |

Every `save_market_organism` call computes a SHA-256 fingerprint of the
composed organism and stores it in the entry:

```
flybrain:organism-v1:31e816588611c82f9d5cbe99f026c707f1e34e9239a723ee1544c6fca149b125
```

Fingerprints are:

- **Deterministic**: same input → same fingerprint
- **Change-sensitive**: any modification changes the fingerprint
- **Stable across order/whitespace**: only semantic differences change it
- **Versioned**: includes pipeline version tag

## 6. Reproducing this document

```bash
# Neuropil grain
python scripts/module_discovery/step1b_neuropil_cluster.py

# Worm cross-species (requires network)
curl -L -o data/worm/raw/herm_chem.zip \
  https://networks.skewed.de/net/celegans_2019/files/hermaphrodite_chemical.csv.zip
curl -L -o data/worm/raw/herm_gap.zip \
  https://networks.skewed.de/net/celegans_2019/files/hermaphrodite_gap_junction.csv.zip
python scripts/module_discovery/step1c_worm_modules.py

# Combinator middleware self-test
python flybrain-connectome-mcp/module_combinator.py

# Fingerprint demo
python scripts/fingerprint_organism.py --compose --modules "sensory,memory"

# Full gate run
python scripts/run_gates.py
```

## 7. Honest boundaries

- The neuropil grain uses `neuropil_stats.json`, which has per-neuropil NT
  distributions but NOT per-(superclass × neuropil) cross-tab. A proper
  junction matrix requires reading the 6.7 GB `syn-partners-male-cns-v1.0.feather`
  with column filtering, which is out of scope for this iteration.
- The worm analysis does not include neurotransmitter annotation (not available
  in Cook 2019), so role-based clustering is the only axis.
- The performance multiplier remains unverified. Structural and combinatorial
  multipliers are the only ones we can honestly claim.
