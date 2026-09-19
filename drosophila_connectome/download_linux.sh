#!/usr/bin/env bash
# Drosophila connectome downloader (MaleCNS / FlyWire)
# Usage: bash download_linux.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/data"
PY="${PYTHON:-python3}"
SCRIPT="$ROOT/scripts/fetch_connectome.py"

echo "=================================================="
echo "  Drosophila connectome downloader (MaleCNS)"
echo "=================================================="
echo "  Out dir: $OUT"
echo

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] python not found (set PYTHON=... to override)"
  exit 1
fi

if [ ! -f "$SCRIPT" ]; then
  echo "[ERROR] missing $SCRIPT"
  exit 1
fi

echo "[1/5] MaleCNS cell annotations (small) ..."
"$PY" "$SCRIPT" flyem-male-cns "v1.0/connectome-data/annotations/" "$OUT/male_cns/annotations" --ext csv,json,tsv,parquet \
  || echo "[WARN] annotations failed - bucket path may have changed"

echo
echo "[2/5] MaleCNS flat-connectome (larger) ..."
"$PY" "$SCRIPT" flyem-male-cns "v1.0/connectome-data/flat-connectome/" "$OUT/male_cns/connectivity" --ext csv,json,tsv,parquet \
  || echo "[WARN] connectivity failed - bucket path may have changed"

echo
echo "[3/5] papers and docs ..."
mkdir -p "$OUT/papers"
curl -sSL --max-time 120 -o "$OUT/papers/google-research-blog.html" \
  "https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/" || true
curl -sSL --max-time 120 -o "$OUT/papers/male-cns-download-page.html" \
  "https://male-cns.janelia.org/download/" || true

echo
echo "[4/5] demo repos ..."
mkdir -p "$OUT/demos"
git clone --depth 1 https://github.com/evnsnclr/neurocraft-fly-public "$OUT/demos/neurocraft-fly-public" || echo "[WARN] clone failed"
git clone --depth 1 https://github.com/MarkUnthank/flyhard "$OUT/demos/flyhard" || echo "[WARN] clone failed"

echo
echo "[5/5] FlyWire probe (dry run, list only) ..."
echo "  NOTE: FlyWire connectivity is best pulled via neuPrint API. See README."
"$PY" "$SCRIPT" flywire "flywire_www/" "$OUT/flywire" --ext csv,json --dry || echo "[WARN] flywire probe failed"

echo
echo "Done. Artifacts in $OUT"
