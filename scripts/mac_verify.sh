#!/usr/bin/env bash
# Reproduce CPU-only synthetic verification on macOS.
# Uses libomp from the local scikit-learn wheel only if system OpenMP is absent.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Virtualenv missing: use Python >=3.10, then pip install -e '.[test,ml]'." >&2
  exit 2
fi
if ! "$PY" -c 'import lightgbm' >/dev/null 2>&1; then
  OMP_DIR="$("$PY" -c 'import sysconfig,pathlib;print(pathlib.Path(sysconfig.get_paths()["purelib"])/"sklearn"/".dylibs")')"
  if [[ ! -f "$OMP_DIR/libomp.dylib" ]]; then
    echo "LightGBM OpenMP runtime missing. Install libomp before continuing." >&2
    exit 2
  fi
  export DYLD_LIBRARY_PATH="$OMP_DIR"
  "$PY" -c 'import lightgbm; print("Using local OpenMP:", lightgbm.__version__)'
fi
echo "=== CPU tests ==="
"$PY" -m pytest -q
BASE="runs/mac_$(date -u +%Y%m%dT%H%M%SZ)"
if [[ $# -gt 0 ]]; then BASE="$1"; fi
for MODEL in factor ridge lightgbm; do
  echo "=== SYNTHETIC demo: $MODEL ==="
  "$PY" -m quant_lab.cli demo --model "$MODEL" --seed 42 --output "$BASE/$MODEL" >/dev/null
done
"$PY" - "$BASE" <<'PY'
from pathlib import Path
import json
import sys
for name in ("factor", "ridge", "lightgbm"):
    p = Path(sys.argv[1]) / name
    m = json.loads((p/"metrics.json").read_text(encoding="utf-8"))
    meta = json.loads((p/"manifest.json").read_text(encoding="utf-8"))
    assert meta["data_kind"] == "SYNTHETIC_DEMO_NOT_REAL_MARKET"
    print(
        f"{name:9} | days {m['days']:3} | OOS RankIC {m['out_of_sample_rank_ic']:+.5f}"
        f" | total net {m['portfolio_net']['total_return']:+.5f}"
        f" | equal-weight net {m['equal_weight_benchmark_net']['total_return']:+.5f}"
    )
print("SYNTHETIC pipeline only; not evidence of market alpha.")
PY
