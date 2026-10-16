# selfverify

**Preregistration as an executable gate.** Turn a frozen preregistration record
into a machine-checked verdict for a computational experiment.

Unlike preregistration *forms* (AsPredicted, OSF-PREREG) which store a promise,
`selfverify` **enforces** it: the gate recomputes its quantity from raw
per-sample records and compares it to the preregistered threshold — an analyst
cannot pass the gate by editing a summary number.

## The four first-class outcomes

| Verdict | Meaning |
|---|---|
| `SUCCESS` | Signal present **and** adequately powered |
| `FAILURE` | Signal absent under the preregistered criterion |
| `WEAK` | Signal present but **under-powered** — do not overclaim |
| `PRE_EXECUTION_REJECTION` | A metric was refused **before** running, because it was analytically redundant with the original |

The last one is the contribution most tools miss: *"we did not run it, because
running it would be uninformative"* is itself a publishable outcome.

## Install

```bash
pip install -e .
```

## Use

```bash
selfverify check --protocol examples/demo_protocol/protocol.json \
                 --results  examples/demo_protocol/results.json
# or
python -m selfverify check --protocol ... --results ... --json
```

## Protocol schema (minimal)

```json
{
  "id": "DEMO-1",
  "hypothesis": "...",
  "metric": "held_out_auc",
  "features": ["..."],
  "success_criteria": {"held_out_auc_min": 0.7, "min_positive_held_out": 3},
  "train_slice": "0:6",
  "held_out_slice": "6:12",
  "reject_rules": [{"type": "coupling", "arm_a": "A", "arm_b": "B", "corr_min": 0.5}]
}
```

## Design principles

1. **Independent recomputation** — the gate reads raw samples, never summaries.
2. **Frozen thresholds** — criteria live in the protocol, not in the script.
3. **Rejection is a result** — pre-execution rejection is first-class.
4. **Zero dependencies** — pure Python (3.9+).

## Difference from AsPredicted / OSF-PREREG

| Dimension | AsPredicted / OSF-PREREG | **selfverify** |
|---|---|---|
| Core artifact | A **form** the analyst fills out | A **frozen record + a gate** that recomputes from raw data |
| Enforcement | Trust-based: reviewers read the form | **Machine**: gate returns FAIL if summary disagrees with raw recompute |
| Refusal category | Silent — analysts either run or quietly drop | **First-class** `PRE_EXECUTION_REJECTION` verdict with justification |
| Negative result | Allowed but discouraged in practice | Enforced as a *valid* verdict, not an error |
| Independence check | Analyst writes "we recomputed this" | Gate *is* the recompute — no summary can be edited to pass |
| Runtime cost | Free (cloud form) | Zero-dependency Python (3.9+), <1s per gate |
| Scope | Any preregistered study | Any *computational* experiment with a score + label per sample |

The core difference: AsPredicted records a **promise**; selfverify enforces it.
The refusal category (`PRE_EXECUTION_REJECTION`) is the sharpest gap — most
preregistration infrastructures have no way to record "we did not run this,
and here is why" as a publishable outcome.

## Design invariants

1. **Independent recomputation** — the gate reads raw samples, never summaries.
2. **Frozen thresholds** — criteria live in the protocol, not in the script.
3. **Rejection is a result** — pre-execution rejection is first-class.
4. **Zero dependencies** — pure Python (3.9+). The gate has no `import`
   outside the standard library; deploy anywhere.
5. **Schema tolerance** — unknown keys in protocol/results JSON are ignored,
   so the schema can grow without breaking older records.

## Origin

Extracted from the `flybrain-connectome` project, where this machinery enforced
gates 43–47 over five preregistered studies (4 negatives + 1 pre-execution
rejection). Generalized here so *any* computational experiment can use it.

Related papers:
- **P-2** — *Preregistered Rejection as a First-Class Negative Result*
- **P-3** — *Four Disciplines for Self-Verification in Computational Experiments*

## License

MIT.
