# F7 · MAS Topology Fault-Injection Benchmark

This is a self-contained benchmark for testing multi-agent system (MAS)
fault-injection behaviour on synthetic communication topologies.

## What it is

- **20 topologies** of 10 nodes each, seeded with 42
- For each topology, a **critical node** is selected (highest degree, ties
  broken by bridge count)
- The critical node is removed to simulate a single-point failure
- Three shutdown strategies are graded: **random / degree / bridge**
- The grading metric is MAE against the actual damage radius
  (= drop_magnitude × 100 from the R1 graded-isolation metric)

## How to use it

1. Load `f7_mas_benchmark.json` — it describes the benchmark card
2. Load `f7_mas_benchmark.csv` — each row is one topology case with
   `actual_damage_radius`, `predicted_random`, `predicted_degree`,
   `predicted_bridge`
3. Run your MAS controller against each topology, record its
   predicted damage radius, and compare MAE against the bridge-based
   baseline

## Success criterion

A MAS controller **beats the bridge strategy** if its MAE is strictly
lower than `bridge` in the `mae` block of the benchmark card.

## Reproduce

```bash
python scripts/f7_mas_benchmark.py --n-topologies 30 --quiet
```
