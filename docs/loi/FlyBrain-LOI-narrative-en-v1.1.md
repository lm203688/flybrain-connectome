# FlyBrain: From Connectome to Programmable Design Substrate

## A Research Overview Prepared for the Mozilla 2027 Fellowship (Track II Independent)

**Applicant:** lm203688 (independent, self-nominated)
**Track:** Track II Independent — $125,000 ($100,000 stipend + $25,000 project), no Host endorsement
**Focus Area:** Neurotech, biotech, physical AI
**Document:** Research overview (narrative), v1.1 — 2026-11-12（v1.1：§4 补 Annual reporting 段，落 GRT 定稿的 "annual progress report" 措辞；v1.0 为初版全文）
**Key dates:** First draft due 2026-11-30 · Submission deadline 2026-12-17

> **How to read this document.** This narrative describes an open research plan. Where a claim rests on measured evidence, the evidence is stated. Where a capability is **not** demonstrated, that absence is stated explicitly rather than glossed. Every quantitative statement in this document is traceable to a repository asset, and the section on honest boundaries (§2.5) lists what FlyBrain does **not** claim.

---

## 1. Problem Statement

The male central nervous system (male CNS) connectome of the fruit fly *Drosophila melanogaster* is among the most complete whole-brain wiring diagrams publicly available in neuroscience. Released as **MaleCNS v1.0** by the Janelia FlyEM team, it comprises **166,700 neurons**, **124,177,617 synapses**, and **25,582,938 directed edges**, published under a **CC-BY** license and cited as **Berg et al., 2026, *Cell* 189(18), 5504–5526.e15, doi:10.1016/j.cell.2026.08.015** (bioRxiv preprint: **doi:10.1101/2025.10.09.680999**). This is a dataset of genuine scale: a full nervous system rendered as an explicit, directed, weighted graph.

The problem is not the availability of the data. The problem is what the field can **do** with it. Today's neuroscience tooling treats a connectome almost exclusively as a **static reference object** — a structure to be queried, mapped, and visually explored. Connectome Workbench, neuPrint, and their peers are, in the most literal sense, retrieval and annotation infrastructure. They answer the question *"what is wired to what?"* They do **not** answer a question that is now becoming actionable: *"if we take real brain wiring as a design template, can we generate, compose, verify, and audit synthetic neural topologies that are traceable back to real neurons and synapses?"*

That gap is the gap FlyBrain is built to fill. No existing project — academic, industrial, or open-source — treats the real connectome as a **programmable design substrate**: a source of structural motifs that can be composed into novel, auditable virtual-biology topologies, with every generated edge carrying machine-readable provenance back to the real connectome data it was derived from. This is **too early**, because full-brain-scale connectomes of this completeness have only been available since 2026 and prior reference datasets were orders of magnitude smaller; **too unexpected**, because the dominant narratives remain either "connectomes for visualization and analysis" or "neural networks designed from scratch," neither of which uses real wiring as a generative template; and **too ambitious**, because it requires combining real data, combinatorial generation, and a verification stack that no existing toolchain currently provides.

FlyBrain does not simulate brain function, and it does not claim to. Its precise, bounded ambition is narrower and, I believe, more fundable: **to convert a real connectome into a programmable, composable, and auditable design substrate, and to build the verification discipline that makes that conversion trustworthy.** That is a contribution at the intersection of Neurotech, biotech, and physical AI — and it is precisely the kind of early, unexpected, and ambitious infrastructure that conventional funders are unlikely to back, because it sits between neuroscience (which funds understanding the brain) and computing (which funds building systems), and belongs fully to neither.

---

## 2. Approach

### 2.1 The core idea

FlyBrain takes **MaleCNS v1.0** as its structural anchor and turns it into a **programmable design substrate**. The connectome is not re-purposed as a simulator and is not reduced to a lookup table. Instead, real wiring statistics are extracted into a library of **functional units**, and those units are composed, under a deterministic and auditable set of rules, into **virtual-biology topologies** — generated structures that are traceable, testable, and open. The system is explicitly a **batch / offline pipeline**, not a real-time or online inference system.

The design rests on a deliberate separation of concerns across four layers:

- **Layer 1 — Data.** MaleCNS v1.0 (~5.63 GB compressed / ~34.85 GB expanded, CC-BY) plus independent cross-species references: *C. elegans* (Witvliet et al., 2020), larval *Drosophila* (Winding et al., 2023), and zebrafish (Petkova et al., 2025, CC-BY-NC-4.0). The primary MaleCNS release is distributed as **211,604 files** under the `DATA_MANIFEST` sha256-verified inventory (211,796 files if generated output is counted).
- **Layer 2 — Module library.** **116 functional units**, each with an explicit capability profile and port types. Units span sensory, memory, motor, integration, attention, working memory, reward, punishment, habit, and metacognition categories. **37 of 116 (31.9%)** are broadly anchored to MaleCNS v1.0 statistics; **12 of 116 (10.3%)** are strictly anchored to measured fruit-fly connectome evidence; the remainder are cross-species literature concept patterns.
- **Layer 3 — Composition engine.** **22 blueprints**, **66 connection types**, and a **combination-reaction engine** with 12 composition rules, 7 nesting levels, and 4 multiplier semantics. Composition occurs at the level of functional units (`compose_from_units`), not at coarse-grained module boundaries. On top of this sits the **virtual-biology morphology generator** (`design_organism`, `evolve_organism`, `render_html`).
- **Layer 4 — Verification.** A five-part verification discipline: **W3C PROV-JSON provenance**, **quality gates**, **pre-registration discipline**, **cross-species validation**, and **fault isolation**.

### 2.2 The verification stack

Auditability is the discipline that distinguishes FlyBrain from a novelty generator, and it is where the work's engineering credibility lives:

- **Provenance (W3C PROV-JSON).** Every generated edge carries machine-readable PROV-JSON provenance tracing its derivation back to the real connectome data. The current implementation passes **70/70 PROV-JSON checks**.
- **Quality gates.** The repository is guarded by a **66-gate** quality gate suite (gates 1–66 in `scripts/run_gates.py`), spanning data integrity, module validity, composition consistency, transport contracts, and documentation drift, with **all gates passing** in the current build.
- **Pre-registration discipline.** The composition engine is subjected to injected-failure pre-registration: **51/51 injection-capture rate (100%; Wilson 95% CI [93.3%, 100.0%])** — the discipline is that injected violations must be caught, and the catch rate is measured rather than asserted.
- **Cross-species validation.** Structural motifs are tested for positive transfer against independently published connectomes: **C. elegans AUC = 1.00 (full pass; kappa = 0.95)**, **larval *Drosophila* AUC = 0.50 (partial)**, and **zebrafish (no signal)**.
- **Fault isolation.** **92.6% module-level fault isolation across 25/27 synthetic topologies** — a property of the generated topologies, not a claim about the real fruit-fly connectome.

### 2.3 The accessible surface

Everything above is reachable through public, standard interfaces. The repository is **MIT-licensed** at `https://github.com/lm203688/flybrain-connectome`. An **interactive demo** is live at `https://lm203688.github.io/flybrain-connectome/demo/`, exposing **36 MCP tools across 58 gate checks**. The **MCP server** (`flybrain-connectome-mcp/mcp_connectome/`) exposes **52 MCP tools plus a parallel HTTP API on port 8799**, so that the full MaleCNS dataset (~5.63 GB compressed / ~34.85 GB expanded) can be queried programmatically without a local download. The project is registered on the **MCP Registry at v3.0.2** (active), while the repository's public shields.io badge is stamped at **v3.01.3**; these are two distinct version dimensions and are reported separately.

### 2.4 Measured results — including what is negative

The project's current results are reported with the same discipline as its claims. Measured and positive: structural simplification of **−84% in line cost (57 → 9)** under a free-form optimizer; functional amplification at **capacity = 3** (three cross-domain closed-loop capability pairs that appear only in combination); **70/70** PROV-JSON checks; **51/51** pre-registration capture; and **C. elegans** cross-species transfer at AUC 1.00.

Measured and **negative** — stated plainly because honesty about null results is part of the methodology: under a matched-control echo-state-network calibration, **0 of 7** topologies outperformed random (differences of 0.001–0.071, all within noise), and under a spiking-neural-network energy harness, **0 of 24** topologies outperformed random. FlyBrain therefore makes **no claim of computational-power or energy advantage**. These negative results are recorded in the repository and are part of the audit trail, not an embarrassment to be omitted.

### 2.5 Honest boundaries

This project is explicit about its limits. The following boundaries are binding on this narrative:

1. **Zero real ground truth for functional validation.** All synthetic-topology validation is based on **structural criteria** (wiring and topology). There are **0 real functional ground-truth benchmarks**. The project holds that **structural criteria are not functional criteria** and makes **no claim of functional validation**.
2. **92.6% fault isolation is a synthetic-topology property.** It was measured on generated topologies (25/27), not on the real fruit-fly connectome, which was not itself subjected to fault-isolation testing.
3. **No BCI/EEG assets.** FlyBrain has **no** brain-computer-interface codebase and **no** neural-signal decoding assets. Its subject is the connectome as a design substrate, not neural signal decoding.
4. **No conformal-prediction precision metric.** Conformal prediction is a capability of a sibling project (SwarmLabs), not FlyBrain; FlyBrain reports no CAP-style precision figures.
5. **No published papers.** Only unsubmitted draft manuscripts exist (e.g., the mainline manuscript draft, v1.2.0). There is **no** published venue, and this document does not describe any paper as "published."
6. **No competition participation.** FlyBrain did **not** enter Neural Interfaces 2026 and has no submission record for it.
7. **Batch / offline system, not real-time.** The project has **no** real-time system validation and is described as a batch pipeline / offline processing system.
8. **No complete EU AI Act compliance claim.** PROV-JSON supports **lineage evidence** only. A residual over-claim in an older demo page is acknowledged and corrected; this document does not assert full EU AI Act compliance.
9. **Data privacy.** The data is non-human connectome data. No human neuroimaging and no personal data are involved, and no ethical restrictions attach to its use.

---

## 3. Impact

**Scientific and academic impact.** FlyBrain establishes the first, explicit pipeline that converts a real, full-scale connectome into a **composable and auditable** design substrate, with a reference citation discipline for the underlying data (Berg et al., 2026, *Cell*). The PROV-JSON provenance layer provides a reusable precedent for making connectome-derived artifacts **auditable**, addressing a gap that affects the whole field: connectome data is released, but derived computational structures rarely carry an auditable derivation record. By publishing the full pipeline under MIT and the data under CC-BY, the project gives the community a reference implementation rather than a one-off demonstration.

**Open-source and infrastructure impact.** Within the 12-month fellowship, FlyBrain will release the complete pipeline — provenance layer, MCP toolchain, and the five-part verification discipline — under an open license, with **MIT** as the preferred candidate. The **52-tool MCP server** and the HTTP API on port 8799 position the connectome as programmable infrastructure: a researcher can query the dataset without a full download, an AI-agent developer can compose topologies with traceable edges, and an educator or student can begin from the interactive demo in minutes. Lowering the barrier to entry for the connectome community is, in itself, an infrastructure contribution.

**Social and governance impact.** The deeper question this work raises is *who gets to decide* how a brain-derived design substrate is used. FlyBrain is built on the principle that control should be returned to the people who actually use the technology. Its open-by-design stance — CC-BY data, MIT code, MCP-standard interfaces, auditable provenance — is intended to support a community model in which the connectome community can inspect, question, and reproduce every derived artifact. That governance-oriented, community-driven stance is central to the work, and it aligns directly with the open-Web, open-source, privacy, and security values that motivate this fellowship.

**What this impact is not.** The impact described here is deliberately bounded. FlyBrain does **not** claim to improve human cognition, does **not** claim any clinical or assistive-device functionality, does **not** claim a computational-power or energy advantage (its measurements there are null), and does **not** claim functional validation of its topologies. The value being offered is open, auditable, structurally rigorous infrastructure at a frontier that is currently unfunded elsewhere.

---

## 4. Timeline

The fellowship runs for **12 months**, from **2027-06-01**. The plan is four milestone phases, each with auditable deliverables (PROV-JSON provenance, quality gates, and pre-registration assertions). **All milestones are planned, not completed**: at the time of this narrative the project stands at repository version **v3.01.3**, with the live demo on an earlier deployed build, and the work described below is the intended 12-month program.

**M1–3 (2027-06 to 2027-08) — Verification-layer expansion and module-library growth.** Expand the topology-verification layer (currently 66 gates, all passing, with 0 of 7 real functional criteria covered) and grow the module library from its current 10 modules toward 15+. Deliverables: module library ≥ 15; functional-amplification verification across ≥ 10 module-combination groups; CI fully green.

**M4–6 (2027-09 to 2027-11) — Cross-species validation and API infrastructure.** Stabilize the connectome-query infrastructure (MCP/HTTP API) and extend cross-species positive-transfer validation, reproducing the *C. elegans* result (AUC 1.00) and extending to additional species. Deliverables: API availability at 99%; documentation covering all 52 tools; a published reproduction of cross-species transfer for ≥ 2 species.

**M7–9 (2027-12 to 2028-02) — System optimization, community, and scholarly output.** Build tutorials and workshops, recruit external contributors, and advance the scholarly manuscript. Deliverables: ≥ 3 tutorials; ≥ 5 external contributors; a manuscript submission from the existing draft line.

**M10–12 (2028-03 to 2028-05) — Deployment, transfer, and closure.** Finalize deployment, publish a complete open-source release, and deliver a full honest-boundary disclosure. Deliverables: open-source package release (PyPI/npm); complete honest-boundary disclosure; a final report of measured results including null findings.

**Annual reporting.** The project will submit an **annual progress report** covering the fellowship year, summarizing the milestones reached, the deliverables shipped, and the measured results — including null findings — consistent with the RFP's delivery requirements. The precise form of that report will be confirmed with Mozilla at the full-application stage.

**Full-time commitment.** The applicant commits to **12 months of full-time** engagement in this fellowship, which applies to both Track I and Track II. Applying as an independent self-nomination, with no institutional host, the applicant will devote full working time to this plan for the full fellowship period, consistent with the RFP's welcome of self-nominations.

---

## 5. Why Mozilla

FlyBrain sits at the intersection that Mozilla's 2027 Call names directly: **Neurotech, biotech, and physical AI**. Connectome-to-programmable-design-substrate is an *open-by-design* practice at the neurotech infrastructure layer — it treats real brain wiring not as a proprietary asset to be mined but as a CC-BY foundation that anyone can query, compose, and audit.

The alignment with Mozilla's mission is concrete rather than rhetorical. Mozilla's commitments to **open Web, open source, privacy, and security** map one-to-one onto FlyBrain's design choices: **open data** (MaleCNS v1.0 under CC-BY), **open code** (MIT), **standard interfaces** (the MCP protocol and a plain HTTP API, so no single vendor gates access), **auditable provenance** (PROV-JSON, so derived artifacts can be inspected), and **honest disclosure** (measured null results published alongside positive ones). The principle that technology should **put control back in the hands of the people who use it** is the governance stance the project is built around, and it is the standard the project applies to itself — including the discipline of stating, in its own documentation, what it cannot yet do.

Most importantly, the **Track II Independent** pathway is what makes this project feasible at all. FlyBrain is an independent effort with **no institutional host**; the $125,000 Track II award provides exactly the 12-month, no-host, self-nominated support the work needs, and the RFP's explicit welcome of self-nominations means this project can be pursued on its own terms rather than contorted to fit an institutional endorsement it does not have. Mozilla is, in practical terms, the one funder whose mission, structure, and review criteria — trailblazing, rigorous, community-driven — are built for exactly this kind of early, unexpected, ambitious, open-infrastructure work.

---

## 6. Open-Source Obligation and Pre-existing IP Boundary

Per the 2027/2028 Fellowship RFP, the Fellow agrees to "release code and non-confidential content **created during the fellowship** under open licenses determined in consultation with Mozilla," and "all copyright, patent, and other proprietary interests in materials produced by selected Fellows in the course of the Fellowship shall be owned by the Fellow."

FlyBrain is a pre-existing project developed before the Fellowship. Its pre-existing assets — Tier-1 components licensed under MIT — together with the third-party MaleCNS connectome data release (© Berg et al. 2026, CC-BY; not created by FlyBrain), and its pre-existing Tier-2 proprietary components (module parameter tables, clustering configurations, and module fingerprint libraries) are not "created during the fellowship" and therefore fall outside the scope of the open-licensing obligation above; no transfer of pre-existing or third-party patent or proprietary interests is implied or required. All content created during the Fellowship — including modifications and extensions of pre-existing code and derived datasets — will be released under open licenses (preferably MIT for code and CC-BY-4.0 for derived data) as determined in consultation with Mozilla. New content will be kept clearly separated from pre-existing IP and recorded in a public IP declaration table in the project README, and Tier-2 proprietary components remain physically isolated in a private repository and are not part of the Fellowship deliverables.

**Honest boundary:** this boundary statement reflects the project's pre-review determination of the scope of the RFP's open-licensing obligation and will be confirmed in the full application.

---

## Appendix: Verification of the numbers cited in this narrative

Every quantitative claim above is traceable to a repository asset. The figures below were re-verified against the repository on 2026-11-12.

| Claim | Value | Source |
|---|---|---|
| Neurons (MaleCNS v1.0) | 166,700 | `male_cns/connectivity_stats.json` |
| Synapses (MaleCNS v1.0) | 124,177,617 | `male_cns/connectivity_stats.json` |
| Directed edges (MaleCNS v1.0) | 25,582,938 | `male_cns/connectivity_stats.json` |
| MaleCNS files (DATA_MANIFEST sha256 inventory) | 211,604 | `DATA_MANIFEST` (211,796 including generated output) |
| PROV-JSON checks | 70/70 | repository verification layer |
| Quality gates | 66 (gates 1–66), all passing | `scripts/run_gates.py` |
| Pre-registration injection capture | 51/51 (100%) | repository verification layer |
| Demo tools / gate checks | 36 MCP tools / 58 gate checks | live demo build |
| MCP server tools | 52 (+ HTTP API :8799) | `flybrain-connectome-mcp/` |
| Functional units / blueprints / connection types | 116 / 22 / 66 | repository module library |
| MCP Registry version | v3.0.2 | MCP Registry entry |
| Repository shields.io badge version | v3.01.3 | repository README badge |
| *C. elegans* / larval / zebrafish | AUC 1.00 / AUC 0.50 / no signal | cross-species validation |
| Fault isolation (synthetic topologies) | 92.6% (25/27) | fault-isolation report |
| Structural simplification | −84% (57 → 9) | GA optimization report |
| Computational-power / energy | 0/7 and 0/24 (null) | matched-control reports |

*This document is a research overview prepared for the Mozilla 2027 Fellowship (Track II Independent). It contains no application action; submission is made by the applicant.*
