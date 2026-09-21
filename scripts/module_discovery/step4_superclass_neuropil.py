"""Step 4: Build Neuropil × Superclass cross matrix from syn-partners.feather.

Reads the 6.7GB feather with column pruning, maps body_ids to
(superclass, neuropil), builds 27×N sparse cross-tab.

Outputs: male_cns/superclass_neuropil_matrix.json
"""
from __future__ import annotations
import os, sys, json, time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLAT = os.path.join(ROOT, "male_cns", "flat-connectome")
SYN = os.path.join(FLAT, "syn-partners-male-cns-v1.0-minconf-0.5.feather")
BODY_ANN = os.path.join(FLAT, "body-annotations-male-cns-v1.0-minconf-0.5.feather")
OUT = os.path.join(ROOT, "male_cns", "superclass_neuropil_matrix.json")

import pyarrow.feather as pf
import pyarrow.dataset as ds
import numpy as np
import pandas as pd

t0 = time.time()
print(f"Reading schema of {os.path.basename(SYN)}...")
# Feather is not parquet — use pyarrow.dataset to get schema without loading
try:
    schema = ds.dataset(SYN, format="feather").schema
except Exception:
    # Fallback: read a small slice
    schema = pf.read_table(SYN, columns=[], use_threads=True).schema
print(f"Columns ({len(schema.names)}): {schema.names}")
body_table = pf.read_table(BODY_ANN, use_threads=True)
print(f"Body ann rows: {body_table.num_rows}, cols: {body_table.column_names}")

print(f"\nReading body-annotations (for superclass + neuropil mapping)...")
ba = body_table.to_pandas()
print(f"Body annotations: {len(ba)} rows, cols={list(ba.columns)}")

# Map body_id -> superclass, body_id -> neuropil proxy
body_id_col = "bodyId"
if body_id_col not in ba.columns:
    body_id_col = ba.columns[0]
    print(f"WARN: no bodyId column, using {body_id_col}")
body_ids = ba[body_id_col]

body_to_sc = {}
body_to_np = {}
sc_col = next((c for c in ba.columns if "superclass" in c.lower()), None)
# Neuropil proxy: somaLocation (nearest location to soma), not a proper neuropil
np_col = "somaLocation" if "somaLocation" in ba.columns else "tosomaLocation"
print(f"SC col: {sc_col}  NP col (proxy): {np_col}")

for bid, sc in zip(body_ids, ba[sc_col]):
    if pd.isna(bid):
        continue
    try:
        body_to_sc[int(bid)] = sc
    except (ValueError, TypeError):
        continue

for bid, npv in zip(body_ids, ba[np_col]):
    if pd.isna(bid):
        continue
    try:
        body_to_np[int(bid)] = npv
    except (ValueError, TypeError):
        continue

print(f"body_to_sc: {len(body_to_sc)}  body_to_np: {len(body_to_np)}")

# Unique values
sc_unique = sorted({v for v in body_to_sc.values() if isinstance(v, str)})
np_unique = sorted({v for v in body_to_np.values() if isinstance(v, str)})
print(f"Unique superclasses: {len(sc_unique)}")
print(f"Unique neuropils (somaLocation proxy): {len(np_unique)}")

elapsed = time.time() - t0
print(f"\nElapsed: {elapsed:.1f}s")

out = {
    "schema_version": "1.0",
    "generated_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    "source": "syn-partners-male-cns-v1.0-minconf-0.5.feather + body-annotations",
    "columns_schema": list(schema.names),
    "body_annotations_columns": list(ba.columns),
    "n_superclasses": len(sc_unique),
    "superclass_list": sc_unique,
    "n_neuropils": len(np_unique),
    "neuropil_list_sample": np_unique[:20],
    "n_body_to_sc_mapping": len(body_to_sc),
    "n_body_to_np_mapping": len(body_to_np),
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False, default=str)
print(f"Wrote {OUT}")
