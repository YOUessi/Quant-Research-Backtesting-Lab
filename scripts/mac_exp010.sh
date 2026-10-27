#!/usr/bin/env bash
# EXP010: local-only original publication-time gate; no model/return/fill edits.
set -euo pipefail
if [[ -n "${QUANT_LAB_ROOT:-}" ]]; then
  ROOT="$QUANT_LAB_ROOT"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Project CPU .venv missing" >&2; exit 2; }

ORIGINALS="data/pit/EXP009_suning_cross_fund_disclosures_20261027"
BROKER="data/pit/EXP008_SZ002024_independent_historical_broker_source_20261027/broker_20210630.html"
REPORT="data/pit/EXP009_suning_two_fund_secondary_halt_evidence_20261027.json"
CAL="data/external/qlib_20261025/calendars/day.txt"
for item in "$ORIGINALS/szse_002024_halt_20210616.html" \
            "$ORIGINALS/rt_shenzhen100_2021_interim.pdf" \
            "$ORIGINALS/zk_wojia_2021_interim.pdf" \
            "$BROKER" "$REPORT" "$CAL"; do
  [[ -f "$item" ]] || { echo "Missing original SHA-verifiable source: $item" >&2; exit 2; }
done
if [[ $# -gt 0 ]]; then BASE="$1"; else BASE="runs/exp010_$(date -u +%Y%m%dT%H%M%SZ)"; fi
[[ ! -e "$BASE" ]] || { echo "Research artifact exists; not overwriting: $BASE" >&2; exit 2; }

"$PY" -m pytest -q
mkdir -p "$BASE"
"$PY" -m quant_lab.pit_source_time_guard \
  --exp009-original-source-report "$REPORT" \
  --original-funds-and-exchange-dir "$ORIGINALS" \
  --broker-original-html "$BROKER" --exchange-calendar "$CAL" \
  --out "$BASE/publication_time_gate.json"
"$PY" - "$BASE/publication_time_gate.json" <<'PY'
import json
import sys
from pathlib import Path
report=json.loads(Path(sys.argv[1]).read_text("utf-8"))
assert report["source_bytes_sha256_rechecked"]
assert report["June_2021_fund_source_day_uses"]==0
assert report["June_2021_primary_halt_start_available_asof_days"]==4
assert report["remaining_reason_specific_original_interval_unresolved"]==5
assert report["prior_original_issuer_full_interval_stock_days_unchanged"]==134
assert report["models_or_frozen_historical_returns_changed"] is False
assert report["source_first_usable_sessions"]=={
    "exchange":"2021-06-17", "broker":"2021-07-01",
    "fund1":"2021-08-30", "fund2":"2021-09-01",
}
print("EXP010 PASS: four original SHA256 files rechecked, zero June fund lookahead.")
print("134/139 original exact intervals unchanged; remaining five not upgraded.")
print("Generated audit is ignored by git:",sys.argv[1])
PY
