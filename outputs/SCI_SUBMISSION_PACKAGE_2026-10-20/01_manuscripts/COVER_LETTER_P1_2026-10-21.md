# Cover Letter — Submission to Scientific Reports / Frontiers in Computational Neuroscience

Dear Editor,

We submit for consideration a methodological paper titled "**A Preregistered-Negative-Result Regime with Machine-Enforced Self-Verification: The 116-Unit Drosophila Male CNS Substrate as Test Case**", targeting *Scientific Reports* as the primary venue and *Frontiers in Computational Neuroscience* as a secondary option. The manuscript is a single-author work by Li Xing (Independent Researcher, Shenzhen, China; ORCID 0000-0002-8747-1969).

## Why this paper, and why now

Computational neuroscience has inherited preregistration from psychology but has not addressed two gaps that are load-bearing in this field. First, the endpoint vocabulary is incomplete: the classical {PASS, FAIL} split has no room for a preregistered *rejection* (a decision not to run a proposed experiment based on a pre-written acceptance rule). Second, preregistration without machine enforcement is prose; the analyst can and does modify thresholds after seeing the data, and the preregistration becomes documentation rather than constraint.

We propose a preregistered-negative-result regime with two formal components: (1) a preregistration four-tuple — predictions, thresholds, execution, verification — with four canonical outcomes (PASS, FAIL, WEAK, REJECT-BEFORE-RUN); (2) four self-verification disciplines (S6–S9) formalized as $(D, \Phi, \sigma)$ triples and enforced by independent gates. The WARNING vs. FAILURE split is a design decision, not a compromise.

We instantiate the regime on seven preregistrations against the 116-unit Drosophila Male CNS substrate and two external connectomes (C. elegans, zebrafish). The endpoint distribution is 1 PASS, 1 WEAK, 5 FAIL, 1 preregistered rejection, 1 PARTIAL. **No FAIL has been silently converted into a PASS.** The S3 mutation-injection battery catches 51/51 seeded defects (Wilson 95% CI [93.0%, 100.0%]), verified against the v2.98.0 baseline of 16/34 (47.1%, CI [31.5%, 63.3%]). Both numbers are reported honestly.

## Why this belongs in your journal

This is a methodology paper, not an empirical paper. Its contribution is the regime itself, not positive findings on the connectome. The negative-result distribution is the honest output of the regime and should not be evaluated as a failure of the method. We target Scientific Reports for its openness to methodological contributions, and Frontiers in Computational Neuroscience for its specialization.

The full pipeline, preregistrations, hash-committed vaults, gates, and reproduction commands are open source at https://github.com/lm203688/flybrain-connectome (MIT License). A reader who pulls the repository and runs three commands in `metrics_fork/` can independently verify the paper's numbers.

## Declarations

- **Conflict of interest**: none.
- **Funding**: none. All experiments were conducted on personal hardware.
- **Ethics**: no human or animal subjects. All data are public connectomics datasets (FlyWire Male CNS v0.1, C. elegans Witvliet 2020, zebrafish Petkova 2025). No IRB approval was required.
- **Data / Code**: https://github.com/lm203688/flybrain-connectome (MIT License)
- **Pre-registration**: all seven protocols preregistered and hash-committed before execution.

## Authorship

Li Xing is the sole author and assumes full responsibility for the design, execution, analysis, and presentation of this research. This is a single-author independent-researcher work, disclosed as a limitation in Discussion §6.6.

We would be honoured to receive the journal's editorial assessment.

Sincerely,

**Li Xing (李星)**  
Independent Researcher · Shenzhen, China  
Email: xingli1123@outlook.com  
ORCID: 0000-0002-8747-1969

Date: 2026-10-21
