#!/usr/bin/env bash
# Execute frozen 2024-2025 Qlib CPU experiment; no output path overwritten.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Create a Python>=3.10 .venv and pip install -e '.[test,ml,qlib]'" >&2
  exit 2
fi
DATA="data/external/qlib_20261025"
MANIFEST="data/downloads/qlib_bin_2026-10-25.manifest.json"
[[ -f "$DATA/instruments/csi300.txt" && -f "$MANIFEST" ]] || {
  echo "Qlib data missing: run bash scripts/install_qlib_release.sh first" >&2
  exit 2
}
if ! "$PY" -c 'import lightgbm' >/dev/null 2>&1; then
  OMP_DIR="$("$PY" -c 'import sysconfig,pathlib;print(pathlib.Path(sysconfig.get_paths()["purelib"])/"sklearn"/".dylibs")')"
  [[ -f "$OMP_DIR/libomp.dylib" ]] || { echo "LightGBM libomp.dylib unavailable" >&2; exit 2; }
  export DYLD_LIBRARY_PATH="$OMP_DIR"
fi
echo "=== Regression tests on Mac CPU ==="
"$PY" -m pytest -q
RUNBASE="runs/real_$(date -u +%Y%m%dT%H%M%SZ)"
if [[ $# -gt 0 ]]; then RUNBASE="$1"; fi
for MODEL in factor ridge lightgbm; do
  echo "=== Qlib historical CSI300 inception-basket / $MODEL ==="
  "$PY" -m quant_lab.real_qlib \
    --provider "$DATA" --source-manifest "$MANIFEST" \
    --start 2024-01-02 --end 2025-12-31 --basket-size 12 \
    --train-days 120 --validation-days 35 --test-days 35 \
    --top-k 3 --fee-bps 10 --seed 42 --model "$MODEL" \
    --output "$RUNBASE/$MODEL" >"/tmp/quant_$MODEL.log"
done
"$PY" -m quant_lab.experiment_analysis \
    --factor-run "$RUNBASE/factor" --ridge-run "$RUNBASE/ridge" \
    --lightgbm-run "$RUNBASE/lightgbm" \
    --fees 0 5 10 20 --top-k 3 --out "$RUNBASE/fee_sensitivity.json"
echo "Audit reports saved in $RUNBASE (gitignored)."
