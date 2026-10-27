#!/usr/bin/env bash
# EXP-009 Mac CPU offline source evidence. NO network, model training or PnL edits.
set -euo pipefail
if [[ -n "$(printenv QUANT_LAB_ROOT || true)" ]]; then ROOT="$(printenv QUANT_LAB_ROOT)"; else ROOT="$(cd "$(dirname "$0")/.." && pwd)"; fi
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Project Python venv missing" >&2; exit 2; }

DATA="data/pit"
FUND="$DATA/EXP009_suning_cross_fund_disclosures_20261027"
BROKER="$DATA/EXP008_SZ002024_independent_historical_broker_source_20261027/broker_20210630.html"
EXP008="$DATA/EXP008_139_memberday_full_source_gate_20261027.json"
PANEL="runs/exp002_data_20261026_v1/dynamic_history.parquet"
CAL="data/external/qlib_20261025/calendars/day.txt"
ISSUER="$DATA/EXP008_35gap_issuer_pdf_candidates_20261027/SZ002024_20220430_one_day.pdf"
RAW="$DATA/139_memberday_market_crosscheck_20261026/independent_unadjusted_market/SZ002024.csv"
RAW_META="$DATA/139_memberday_market_crosscheck_20261026/summary.json"
for FILE in "$FUND/rt_shenzhen100_2021_interim.pdf" "$FUND/zk_wojia_2021_interim.pdf" "$FUND/szse_002024_halt_20210616.html" "$BROKER" "$EXP008" "$PANEL" "$CAL" "$ISSUER" "$RAW" "$RAW_META"; do
  [[ -f "$FILE" ]] || { echo "ABORT: source missing: $FILE" >&2; exit 2; }
done
if [[ $# -gt 0 ]]; then BASE="$1"; else BASE="runs/exp009_$(date -u +%Y%m%dT%H%M%SZ)"; fi
[[ ! -e "$BASE" ]] || { echo "Refusing overwrite: $BASE" >&2; exit 2; }
if [[ -n "$(printenv EXTRA_TEST_DIR || true)" ]]; then
  "$PY" -m pytest -q --import-mode=importlib tests "$(printenv EXTRA_TEST_DIR)"
else
  "$PY" -m pytest -q
fi
mkdir -p "$BASE"

"$PY" -m quant_lab.pit_fund_suspension_evidence \
  --original-funds-and-exchange-dir "$FUND" \
  --broker-original-html "$BROKER" \
  --prior-exp008 "$EXP008" --historical-panel "$PANEL" --calendar "$CAL" \
  --out "$BASE/two_fund_retrospective_halt.json"

"$PY" -m quant_lab.pit_st_limit_exploratory \
  --original-st-pdf "$ISSUER" --independent-raw-daily "$RAW" \
  --independent-source-meta "$RAW_META" --exchange-calendar "$CAL" \
  --out "$BASE/original_issuer_ST_5pct_one_price_down.json"

"$PY" - "$BASE" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
f=json.loads((root/"two_fund_retrospective_halt.json").read_text())
s=json.loads((root/"original_issuer_ST_5pct_one_price_down.json").read_text())
assert f["original_issuer_or_exchange_FULL_interval_verified_days_retained"]==134
assert f["new_additional_fund_original_retrospective_only_corrob_days"]==5
assert f["total_member_days_with_original_primary_interval_or_independent_fund_retrospective_evidence"]==139
assert f["fund_original_disclosure_count"]==2
assert f["primary_original_issuer_first_five_day_segment_end_date_still_unverified"]
assert s["n_historical_consecutive_one_price_down_sessions"]==3
assert [x["derived_limit_down_price_NOT_OFFICIAL"] for x in s["one_price_down_session_details"]]==["3.07","2.92","2.77"]
assert not s["actual_open_auction_sell_queue_fills_observed"]
print("EXP009 REPRODUCED: primary issuer 134/139; extra 5 fund retrospective only.")
print("ST original 5% issuer + actual raw 3 one-price down days.")
print("Broker fills NOT CERTIFIED; original PDFs/raw quotes remain locally gitignored:",root)
PY
