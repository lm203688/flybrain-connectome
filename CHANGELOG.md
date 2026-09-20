# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The **schema version** is versioned separately from the **package version**:

| | value | meaning |
|---|---|---|
| package | `1.0.0` | the toolkit as a whole |
| schema (organism / swarm config) | `1.2.1` | top-level generated-document shape |
| schema (`motif_provenance` block) | `1.2.0` | provenance sub-document; unchanged since v1.2.0 |

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
