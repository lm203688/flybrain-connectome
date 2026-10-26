#!/usr/bin/env python3
"""Generate SCI-required figures and tables for P-1 mainline manuscript.

Outputs:
  figures/fig1_prereg_endpoint_distribution.png
  figures/fig2_s3_injection_catch_rate.png
  figures/fig3_s1_external_validation_auc.png
  figures/table1_seven_preregistrations.md (markdown source)
  figures/table2_research_claims_stats.md
  figures/table3_s1_external_validation.md
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FIGDIR = ROOT / "outputs" / "SCI_SUBMISSION_PACKAGE_2026-10-20" / "06_latex_manuscript" / "p1_mainline" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

# Journal-standard figure style
plt.rcParams.update({
    "figure.dpi": 300,
    "figure.constrained_layout.use": True,
    "font.size": 10,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.2,
    "grid.linestyle": "--",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})


# ---------------------------------------------------------------------------
# Figure 1 — Seven preregistrations, endpoint distribution
# ---------------------------------------------------------------------------
def fig1_prereg_endpoints():
    labels = [
        "PR-1\nMechanism",
        "PR-2\nIntervention",
        "PR-3 v2\nGeneralization",
        "PR-4\nRecovery dyn.",
        "PR-2b\nPre-exec reject",
        "PR_S1\nExternal val.",
        "PR_S2\nLesion cascade",
    ]
    endpoints = ["WEAK", "FAIL", "FAIL", "PASS", "REJECT", "PARTIAL", "FAIL"]
    colors = {
        "PASS": "#2a7b2a",
        "WEAK": "#e8a800",
        "FAIL": "#c0392b",
        "REJECT": "#7b2cbf",
        "PARTIAL": "#0073ad",
    }
    counts = [endpoints.count(k) for k in ["PASS", "WEAK", "PARTIAL", "REJECT", "FAIL"]]
    cats = ["PASS", "WEAK", "PARTIAL", "REJECT", "FAIL"]

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.4, 1]})

    # Left: horizontal bar of endpoints per prereg
    for i, (lab, ep) in enumerate(zip(labels, endpoints)):
        axA.barh(i, 1, color=colors[ep], edgecolor="none")
        axA.text(1.02, i, ep, va="center", fontsize=9, color=colors[ep], fontweight="bold")
    axA.set_yticks(range(len(labels)))
    axA.set_yticklabels(labels, fontsize=8)
    axA.set_xlim(0, 1.5)
    axA.set_xticks([])
    axA.invert_yaxis()
    axA.set_title("Per-preregistration endpoint", fontsize=10)
    axA.grid(False)

    # Right: stacked horizontal bar of endpoint counts
    left = 0
    total = sum(counts)
    for cat, n in zip(cats, counts):
        axB.barh(0, n, left=left, color=colors[cat], edgecolor="white")
        if n > 0:
            axB.text(left + n / 2, 0, f"{n}\n{cat}", ha="center", va="center",
                     fontsize=9, color="white" if cat in ("FAIL", "PASS", "REJECT") else "black",
                     fontweight="bold")
        left += n
    axB.set_yticks([])
    axB.set_xticks([i for i in range(total + 1)])
    axB.set_title("Endpoint distribution (n=7)", fontsize=10)
    axB.grid(False)
    axB.set_xlabel("count")

    fig.suptitle("Figure 1.  The seven preregistrations and their canonical outcomes",
                 fontsize=11, y=1.02, fontweight="bold")
    fig.text(0.01, -0.02,
             "PR-2b is a preregistered rejection (never executed). PR_S1 and PR_S2 are "
             "post-suite boundary probes. All verdicts frozen at preregistration time.",
             fontsize=8, style="italic")
    out = FIGDIR / "fig1_prereg_endpoint_distribution.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 2 — S3 mutation-injection catch-rate (51/51)
# ---------------------------------------------------------------------------
def fig2_s3_injection():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1.4, 1]})

    # Left: v2.98.0 baseline vs v2.98.1 post-hardening
    baseline_caught, baseline_total = 16, 34
    hardened_caught, hardened_total = 51, 51
    baseline_rate = baseline_caught / baseline_total * 100
    hardened_rate = hardened_caught / hardened_total * 100

    # Wilson 95% CI
    from math import sqrt, log
    def wilson(k, n, z=1.96):
        if n == 0: return (0, 0)
        p = k / n
        denom = 1 + z*z / n
        center = (p + z*z / (2*n)) / denom
        half = z * sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
        return max(0, (center - half) * 100), min(100, (center + half) * 100)

    b_lo, b_hi = wilson(baseline_caught, baseline_total)
    h_lo, h_hi = wilson(hardened_caught, hardened_total)

    bars = [
        ("v2.98.0\nbaseline", baseline_rate, baseline_caught, baseline_total, b_lo, b_hi, "#e8a800"),
        ("v2.98.1\npost-hardening", hardened_rate, hardened_caught, hardened_total, h_lo, h_hi, "#2a7b2a"),
    ]
    x = np.arange(len(bars))
    for i, (lab, rate, k, n, lo, hi, col) in enumerate(bars):
        axA.bar(i, rate, color=col, edgecolor="black", linewidth=0.6, width=0.5)
        lo_safe = min(lo, rate)
        hi_safe = max(hi, rate)
        axA.errorbar(i, rate, yerr=[[rate - lo_safe], [hi_safe - rate]], fmt="none",
                     ecolor="black", capsize=5, linewidth=1.2)
        axA.text(i, rate + 3, f"{k}/{n} = {rate:.1f}%", ha="center", fontsize=9, fontweight="bold")
        axA.text(i, rate / 2, f"CI [{lo:.1f}, {hi:.1f}]", ha="center", fontsize=8, color="white")
    axA.set_xticks(x)
    axA.set_xticklabels([b[0] for b in bars], fontsize=9)
    axA.set_ylim(0, 115)
    axA.set_ylabel("catch-rate (%)")
    axA.set_title("S3 discipline-effectiveness: gate catch-rate", fontsize=10)
    axA.axhline(100, color="gray", linestyle=":", linewidth=1, label="100% catch")
    axA.axhline(50, color="gray", linestyle=":", linewidth=1)
    axA.legend(fontsize=8, loc="lower right")

    # Right: W1-W7 gate-defect closure table (bar)
    defect_labels = ["W1\nPR1 seed", "W2\nPR2b reject", "W3\nPR2b dir", "W4\nPR3 family",
                     "W5\nPR3 v2 family", "W6\nC3 AUC", "W7\nPR_S1 vault"]
    defects_closed = [1, 1, 1, 1, 1, 1, 1]
    axB.bar(defect_labels, defects_closed, color="#7b2cbf", edgecolor="black", linewidth=0.5)
    axB.set_yticks([0, 0.5, 1])
    axB.set_yticklabels(["open", "", "closed"])
    axB.set_ylabel("W-defect closure")
    axB.set_title("7 gate defects closed (W1-W7)", fontsize=10)
    for i, d in enumerate(defects_closed):
        axB.text(i, d + 0.03, "closed", ha="center", fontsize=8, color="#7b2cbf", fontweight="bold")

    fig.suptitle("Figure 2.  S3 mutation-injection battery: 51/51 catch-rate after W1-W7 closure",
                 fontsize=11, y=1.02, fontweight="bold")
    fig.text(0.01, -0.02,
             "Wilson 95% CI computed with z=1.96. Injection battery grew from 34 to 51 "
             "injections between v2.98.0 and v2.98.1 as W1-W7 gate defects were closed.",
             fontsize=8, style="italic")
    out = FIGDIR / "fig2_s3_injection_catch_rate.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 3 — S1 external validation AUC across 3 datasets
# ---------------------------------------------------------------------------
def fig3_s1_external():
    with open(ROOT / "_s1_external_validation" / "results.json") as fp:
        s1 = json.load(fp)
    c3 = s1.get("c3_results", {})

    internal_families = ["project_synthetic", "erdos_renyi", "barabasi_albert",
                         "watts_strogatz", "malecns_subgraph"]
    external_families = ["cel", "larva", "zebrafish"]

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.2))

    # Left: AUC comparison by family (n=20 slice if available, else n=10)
    n_slice = "n=20" if any("n=20" in c3.get(f, {}) for f in internal_families) else "n=10"
    fams = internal_families + external_families
    auvs, los, his, styles = [], [], [], []
    for f in fams:
        entry = c3.get(f, {}).get(n_slice)
        if entry:
            auvs.append(entry.get("auc", np.nan))
            los.append(entry.get("auc_ci_low", np.nan))
            his.append(entry.get("auc_ci_high", np.nan))
            styles.append("solid" if f in internal_families else "hatched")
        else:
            auvs.append(np.nan); los.append(np.nan); his.append(np.nan); styles.append("solid")

    colors = ["#4a90e2"] * len(internal_families) + ["#c0392b"] * len(external_families)
    hatches = [""] * len(internal_families) + ["/"] * len(external_families)

    x = np.arange(len(fams))
    yerr_lo = [a - l for a, l in zip(auvs, los)]
    yerr_hi = [h - a for a, h in zip(auvs, his)]
    bars = axA.bar(x, auvs, color=colors, edgecolor="black", linewidth=0.6, width=0.65)
    for i, h in enumerate(hatches):
        if h: bars[i].set_hatch(h)
    axA.errorbar(x, auvs, yerr=[yerr_lo, yerr_hi], fmt="none", ecolor="black",
                 capsize=4, linewidth=1)
    axA.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="chance (AUC=0.5)")
    axA.axhline(0.7, color="orange", linestyle=":", linewidth=1, label="PASS threshold (0.70)")
    axA.set_xticks(x)
    axA.set_xticklabels(fams, fontsize=7.5, rotation=25, ha="right")
    axA.set_ylim(0, 1.1)
    axA.set_ylabel("AUC")
    axA.set_title(f"C3 AUC by family ({n_slice})", fontsize=10)
    axA.legend(fontsize=8, loc="lower left")

    # Right: internal vs external aggregate
    int_aucs = [v for v, f in zip(auvs, fams) if f in internal_families and not np.isnan(v)]
    ext_aucs = [v for v, f in zip(auvs, fams) if f in external_families and not np.isnan(v)]
    agg = np.array([np.mean(int_aucs), np.mean(ext_aucs)])
    axB.bar(["Internal\n(5 families)", "External\n(3 datasets)"], agg,
            color=["#4a90e2", "#c0392b"], edgecolor="black", linewidth=0.6)
    axB.axhline(0.7, color="orange", linestyle=":", linewidth=1, label="PASS threshold")
    for i, v in enumerate(agg):
        axB.text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=10, fontweight="bold")
    axB.set_ylim(0, 1.1)
    axB.set_ylabel("mean AUC")
    axB.set_title("Internal vs. external aggregate", fontsize=10)
    axB.legend(fontsize=8)

    fig.suptitle("Figure 3.  S1 external validation: C3 AUC across internal and external connectomes",
                 fontsize=11, y=1.02, fontweight="bold")
    fig.text(0.01, -0.02,
             "Larva dataset loaded as a structural-only placeholder (n=0 edges); "
             "AUC undefined. Verdict is PARTIAL because external AUC does not meet "
             "the preregistered 0.70 threshold.",
             fontsize=8, style="italic")
    out = FIGDIR / "fig3_s1_external_validation_auc.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Table 1 — Seven preregistrations
# ---------------------------------------------------------------------------
def table1_seven_prereg():
    rows = [
        ["PR-1", "Mechanism predictability", "200 permutations", "0.788", "z=1.5291", "p=0.1262", "WEAK"],
        ["PR-2", "Intervention effect", "n=10/50/100", "composite 38.9→71.4→59.1", "n/a", "n/a", "FAIL"],
        ["PR-3 v1", "Generalization (n=10)", "5 families", "2/5 pass", "n/a", "n/a", "FAIL"],
        ["PR-3 v2", "Generalization w/ quantile labels", "5 families", "n/a", "n/a", "n/a", "FAIL"],
        ["PR-4", "Recovery dynamics", "n=1000", "560/1000", "Wilson [0.5291, 0.5905]", "p≈0.00015", "PASS"],
        ["PR-2b", "Pre-execution rejection", "n/a (not run)", "n/a", "n/a", "n/a", "REJECT"],
        ["PR_S1", "Cross-species external validation", "3 datasets", "PARTIAL (mean AUC)", "bootstrap CI", "n/a", "PARTIAL"],
        ["PR_S2", "Lesion cascade w/ Xu 2026 bridge", "500 bootstrap", "d=1.153, ρ=-0.1795", "bootstrap", "p=0.0149", "FAIL"],
    ]
    lines = []
    lines.append("| Protocol | Focus | Design | Effect | CI | p-value | Verdict |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    out = FIGDIR / "table1_seven_preregistrations.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Table 2 — Research claims top-level statistics
# ---------------------------------------------------------------------------
def table2_research_claims():
    with open(ROOT / "research_claims.json") as fp:
        d = json.load(fp)
    lines = ["| Claim | Status | Point est. | 95% CI | p-value | Test |",
             "|---|---|---|---|---|---|"]
    for c in d["claims"]:
        pe = c.get("point_estimate")
        lo = c.get("ci_low")
        hi = c.get("ci_high")
        pv = c.get("p_value")
        tn = c.get("test_name", "")
        ci_str = f"[{lo}, {hi}]" if lo is not None and hi is not None else "n/a"
        pe_str = f"{pe:.4f}" if isinstance(pe, (int, float)) else str(pe)
        pv_str = f"{pv:.4f}" if isinstance(pv, (int, float)) else str(pv)
        tn_short = (tn or "")[:40]
        lines.append(f"| {c['id']} | {c['status']} | {pe_str} | {ci_str} | {pv_str} | {tn_short} |")
    out = FIGDIR / "table2_research_claims_stats.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Table 3 — S1 external validation
# ---------------------------------------------------------------------------
def table3_s1_external():
    with open(ROOT / "_s1_external_validation" / "results.json") as fp:
        s1 = json.load(fp)
    c3 = s1.get("c3_results", {})
    lines = ["| Dataset | Origin | n (n=20 slice) | AUC | CI | Verdict |",
             "|---|---|---|---|---|---|"]
    meta = s1.get("dataset_meta", {})
    for f in ["cel", "larva", "zebrafish"]:
        entry = c3.get(f, {}).get("n=20", {})
        n_samples = entry.get("n_samples", "—")
        auc = entry.get("auc", "—")
        lo = entry.get("auc_ci_low", "—")
        hi = entry.get("auc_ci_high", "—")
        auc_s = f"{auc:.4f}" if isinstance(auc, (int, float)) else str(auc)
        lo_s = f"{lo:.4f}" if isinstance(lo, (int, float)) else str(lo)
        hi_s = f"{hi:.4f}" if isinstance(hi, (int, float)) else str(hi)
        ci_s = f"[{lo_s}, {hi_s}]" if auc != "—" else "n/a"
        m = meta.get(f, {})
        origin = f"{m.get('species','?')} / {m.get('source','?')}"
        lines.append(f"| {f} | {origin} | {n_samples} | {auc_s} | {ci_s} | — |")
    out = FIGDIR / "table3_s1_external_validation.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main():
    print("Building SCI figures and tables...")
    outputs = [
        fig1_prereg_endpoints(),
        fig2_s3_injection(),
        fig3_s1_external(),
        table1_seven_prereg(),
        table2_research_claims(),
        table3_s1_external(),
    ]
    for p in outputs:
        sz = p.stat().st_size
        kind = "FIG" if p.suffix == ".png" else "TBL"
        print(f"  [{kind}] {p.name}: {sz/1024:.1f} KB")


if __name__ == "__main__":
    main()
