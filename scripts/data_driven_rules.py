"""
Data-driven combination-rule discovery (层2 补强).

Instead of hand-picking allowed superclass→superclass connections, this script
derives *candidate* rules directly from the real MaleCNS connectome:

  1. Load male_cns/superclass_matrix.json (27×27 synapse-percentage matrix).
  2. Build an independence (null) model: expected_{ij} = rowFrac_i * colFrac_j.
  3. Enrichment  = observed_{ij} / expected_{ij}.
  4. Significance: z = (obs - exp) / sqrt(exp)  (Poisson approximation).
  5. Rank pairs by enrichment (with a floor on observed % to suppress noise),
     categorise each superclass into a functional role, and emit candidate
     rules that the curated COMBINATION_RULES can be checked against.

Output: male_cns/candidate_combination_rules.json

This is a *discovery* tool: it surfaces which wirings are over-represented in
the real brain, giving an evidence base for the hand-curated rule table
(so the 12 curated rules can be audited: which are supported by data, which
are pure hypothesis).
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "male_cns" / "superclass_matrix.json"
OUT = ROOT / "male_cns" / "candidate_combination_rules.json"

# ---- functional category heuristic (documented, approximate) ---------------- #
def categorize(sc: str) -> str:
    s = sc.lower()
    if s.endswith("_sensory"):
        return "sensory_input"
    if "intrinsic" in s:
        return "recurrent_memory"
    if s.endswith("_motor"):
        return "motor"
    if "endocrine" in s or s.endswith("_efferent") or "efferent" in s:
        return "modulation"
    if "visual" in s:
        return "sensory_transform"
    if s in ("ascending_neuron", "descending_neuron", "sensory_ascending",
             "sensory_descending") or s.endswith("_tbc") or s == "ens":
        return "relay" if s != "ens" else "enteric"
    return "relay"


def main() -> int:
    d = json.loads(MATRIX.read_text(encoding="utf-8"))
    sl = d["superclass_list"]
    n = len(sl)
    pct = d["matrix_pct"]                 # pct[i][j] = % of ALL synapses i→j
    total = d["total_synapses"]

    # marginals (as fractions 0..1)
    row_frac = [sum(pct[i]) / 100.0 for i in range(n)]   # out-degree share of i
    col_frac = [sum(pct[i][j] for i in range(n)) / 100.0 for j in range(n)]  # in-degree share of j

    candidates = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            obs_pct = pct[i][j]
            exp_pct = row_frac[i] * col_frac[j] * 100.0
            if exp_pct <= 0:
                continue
            enrichment = obs_pct / exp_pct
            obs_count = obs_pct / 100.0 * total
            exp_count = exp_pct / 100.0 * total
            import math
            z = (obs_count - exp_count) / math.sqrt(max(exp_count, 1.0))
            candidates.append({
                "from_superclass": sl[i],
                "to_superclass": sl[j],
                "from_category": categorize(sl[i]),
                "to_category": categorize(sl[j]),
                "observed_pct": round(obs_pct, 4),
                "expected_pct": round(exp_pct, 4),
                "enrichment": round(enrichment, 3),
                "z_score": round(z, 2),
                "observed_synapses": int(round(obs_count)),
            })

    # Floor: ignore pairs with < 0.05% of all synapses (noise)
    FLOOR = 0.05
    strong = [c for c in candidates if c["observed_pct"] >= FLOOR and c["enrichment"] >= 1.5]
    strong.sort(key=lambda c: (c["enrichment"], c["observed_pct"]), reverse=True)

    result = {
        "schema_version": "1.2.2",
        "source": "MaleCNS v1.0 superclass synapse matrix (27×27)",
        "null_model": "independence: expected_ij = outFrac_i * inFrac_j",
        "total_synapses": total,
        "filters": {"min_observed_pct": FLOOR, "min_enrichment": 1.5},
        "candidate_count": len(strong),
        "candidates": strong,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # console summary
    print(f"loaded matrix: {n} superclasses, total={total:,} synapses")
    print(f"null model: independence (expected_ij = outFrac_i * inFrac_j)")
    print(f"candidates passing floor (obs>= {FLOOR}%, enrichment>=1.5): {len(strong)}")
    print("\nTop 15 over-represented wirings (data-driven candidate rules):")
    print(f"  {'from':<22}{'to':<22}{'obs%':>8}{'exp%':>8}{'enr':>7}{'z':>9}{'syn':>13}")
    for c in strong[:15]:
        print(f"  {c['from_superclass']:<22}{c['to_superclass']:<22}"
              f"{c['observed_pct']:>8.3f}{c['expected_pct']:>8.3f}"
              f"{c['enrichment']:>7.2f}{c['z_score']:>9.1f}{c['observed_synapses']:>13,}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
