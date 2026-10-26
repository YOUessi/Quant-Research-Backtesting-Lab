#!/usr/bin/env bash
# EXP-002 exact preregistered historical research, Mac CPU only.
# WARNING: Qlib source adjustment factors are not point-in-time certified.
set -euo pipefail
if [[ -n "$QUANT_LAB_ROOT" ]]; then
  ROOT="$QUANT_LAB_ROOT"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Requires isolated Python 3.10+ .venv" >&2; exit 2; }
"$PY" -c 'import qlib, pyarrow; print("Qlib/Parquet dependency OK:", qlib.__version__)'
if [[ ! -f data/external/qlib_20261025/instruments/csi300.txt ]]; then
  echo "Pinned Qlib source missing: run bash scripts/install_qlib_release.sh" >&2
  exit 2
fi
[[ -f data/downloads/qlib_bin_2026-10-25.manifest.json ]] || {
  echo "Same-release Qlib source manifest missing" >&2
  exit 2
}
if [[ $# -gt 0 ]]; then
  BASE="$1"
else
  BASE="runs/exp002_$(date -u +%Y%m%dT%H%M%SZ)"
fi
if [[ -e "$BASE" ]]; then
  echo "Refusing to overwrite existing experiment output: $BASE" >&2
  exit 2
fi
echo "EXP-002 preregistered full CSI300 historical-membership research"
"$PY" -m pytest -q
"$PY" -m quant_lab.exp002 data \
  --provider data/external/qlib_20261025 \
  --source-manifest data/downloads/qlib_bin_2026-10-25.manifest.json \
  --output "$BASE/data" > /tmp/quant_exp002_last_data_stdout.log
"$PY" -m quant_lab.exp002 simulate \
  --data "$BASE/data" \
  --output "$BASE/execution" > /tmp/quant_exp002_last_exec_stdout.log
"$PY" -m quant_lab.index_reference \
  --provider data/external/qlib_20261025 \
  --source-manifest data/downloads/qlib_bin_2026-10-25.manifest.json \
  --out "$BASE/execution/CSI300_price_reference.json" > /tmp/quant_exp002_last_index_stdout.log
"$PY" - "$BASE" <<'PY'
import json,sys
from pathlib import Path
base=Path(sys.argv[1])
members=json.loads((base/"data/audit.json").read_text())["membership"]
results=json.loads((base/"execution/EXP002_SUMMARY.json").read_text())
print("Historical union:",members["n_ever_index_members"])
print("Member-day missing/invalid:",members["member_day_missing_or_invalid_close"])
for key,value in results["models"].items():
    print(key,value["status"],value.get("cum_total_return_proxy","WITHHELD"))
print("PIT corporate-action adjustment certified:",results["independent_factor_history_snapshots_present"])
print("Raw market data and event logs stay in gitignored runs/.")
PY
