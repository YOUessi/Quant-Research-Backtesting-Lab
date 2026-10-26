#!/usr/bin/env bash
# Offline EXP007–008 source integrity, stock-share rights, issuer halt, nominal
# marks and limited historical ST rule evidence. Mac CPU; no model tuning.
#
# Requires earlier original-PDF local archives, Qlib and independently obtained
# unadjusted daily CSVs. Refuses to create synthetic substitutes or overwrite
# immutable research output. Does not download sources or publish raw PDFs.
set -euo pipefail

if [[ -n "$(printenv QUANT_LAB_ROOT || true)" ]]; then
  ROOT="$(printenv QUANT_LAB_ROOT)"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"
PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Python>=3.10 project venv required. Install -e '.[test,ml,qlib,audit]'." >&2
  exit 2
fi
if [[ -n "$(printenv EXP_SOURCE_ROOT || true)" ]]; then
  export PYTHONPATH="$(printenv EXP_SOURCE_ROOT)"
fi
if [[ -n "$(printenv EXTRA_TEST_DIR || true)" ]]; then
  "$PY" -m pytest -q --import-mode=importlib tests "$(printenv EXTRA_TEST_DIR)"
else
  "$PY" -m pytest -q
fi
if [[ $# -gt 0 ]]; then
  BASE="$1"
else
  BASE="runs/exp007_008_$(date -u +%Y%m%dT%H%M%SZ)"
fi
if [[ -e "$BASE" ]]; then
  echo "A frozen run already exists: $BASE" >&2
  exit 2
fi
mkdir -p "$BASE"
CASH="data/pit/EXP005_issuer_cash_action_ledger_v3_20261027.json"
P19="data/pit/issuer_batch19_20261026/issuer_pdfs"
P30="data/pit/issuer_batch30_random_20261026/issuer_pdfs"
P0="data/pit/issuer_official_20261026/raw_official_pdfs"
VENDOR="data/pit/csi300_dynamic_2021_22_20261026"
PANEL="runs/exp002_data_20261026_v1/dynamic_history.parquet"
CAL="data/external/qlib_20261025/calendars/day.txt"
HALT="data/pit/EXP005_rights_issue_halts_20261027.json"
RAW="data/pit/EXP007_additional_unadjusted_daily_quotes_20261027"

for FILE in "$CASH" "$PANEL" "$CAL" "$HALT" \
  "$RAW/SH600276_2021-06-10_raw.csv" \
  "$RAW/SH600760_2021-06-24_raw.csv" \
  "$RAW/SH603392_2022-04-21_raw.csv" \
  "data/pit/EXP007_additional_resume_pdfs_20261027/combined_issuer_audit.json" \
  "data/pit/EXP005_official_halt_17_20261027/source_audit.json"; do
  if [[ ! -f "$FILE" ]]; then
    echo "Source-proven real historical input missing: $FILE" >&2
    exit 2
  fi
done

"$PY" -m quant_lab.pit_share_distribution \
  --cash-ledger "$CASH" --issuer-pdfs "$P19" "$P30" "$P0" \
  --aggregator-dir "$VENDOR" \
  --out "$BASE/original_issuer_stock_rights.json"

"$PY" -m quant_lab.pit_capital_balance \
  --cash-ledger "$CASH" \
  --share-audit "$BASE/original_issuer_stock_rights.json" \
  --issuer-dirs "$P19" "$P30" "$P0" \
  --out "$BASE/original_issuer_capital_balance.json"

"$PY" -m quant_lab.pit_rights_catalog \
  --cash-ledger "$CASH" \
  --share-audit "$BASE/original_issuer_stock_rights.json" \
  --capital-proof "$BASE/original_issuer_capital_balance.json" \
  --out "$BASE/original_issuer_combined_catalog.json"

"$PY" -m quant_lab.pit_listing_availability \
  --rights-catalog "$BASE/original_issuer_combined_catalog.json" \
  --issuer-dirs "$P19" "$P30" "$P0" \
  --out "$BASE/original_issuer_bonus_listing_schedule.json"

"$PY" -m quant_lab.pit_halt_pairs \
  --issuer-archive data/pit/EXP007_additional_resume_pdfs_20261027/combined_issuer_audit.json \
  --original-issuer-pdfs data/pit/EXP007_additional_resume_pdfs_20261027/original_issuer_pdfs \
  --historical-panel "$PANEL" --calendar "$CAL" \
  --previous-rights-halt "$HALT" \
  --out "$BASE/source_issuer_full_halt_intervals.json"

"$PY" -m quant_lab.pit_multi_nominal_rights \
  --rights-catalog "$BASE/original_issuer_combined_catalog.json" \
  --source-daily-dir "$RAW" \
  --out "$BASE/three_unadjusted_stock_bonus_cash_marks"

"$PY" -m quant_lab.pit_exp008_original_proofs \
  --new-original-pdf-folder data/pit/EXP008_35gap_issuer_pdf_candidates_20261027 \
  --old-original-issuer-pdf-folder data/pit/EXP005_official_halt_17_20261027/original_issuer_pdfs \
  --historical-panel "$PANEL" --exchange-calendar "$CAL" \
  --augmented-prior-halt "$BASE/source_issuer_full_halt_intervals.json" \
  --previous-rights-halt "$HALT" \
  --out "$BASE/final_139_missing_security_sessions.json"

"$PY" - "$BASE" <<'PY'
import json,sys
from pathlib import Path
base=Path(sys.argv[1])
files={
 "catalog":base/"original_issuer_combined_catalog.json",
 "listing":base/"original_issuer_bonus_listing_schedule.json",
 "halt":base/"source_issuer_full_halt_intervals.json",
 "prices":base/"three_unadjusted_stock_bonus_cash_marks"/"audit.json",
 "exp008":base/"final_139_missing_security_sessions.json",
}
a={key:json.loads(p.read_text("utf-8")) for key,p in files.items()}
assert a["catalog"]["issuer_events"]==89
assert a["catalog"]["fully_verified_nominal_share_rights"]==27
assert a["listing"]["issuer_listing_days_confirmed"]==6
assert a["halt"]["unique_issuer_proven_halted_stock_session_union"]==104
assert a["prices"]["n_reconciled_publisher_rights_events"]==3
assert a["exp008"]["total_issuer_documented_halt_stock_days"]==134
assert a["exp008"]["still_missing_original_verified_stoppage_or_resume_source"]==5
assert not a["exp008"]["actual_issuer_daily_price_limit_levels_fetched"]
assert not a["exp008"]["realized_broker_order_receipts_fetched"]
print("EXP007–008 ACCEPTED EVIDENCE AUDIT:")
print("  original issuer cash events: 89")
print("  fully supported nominal share rights: 27")
print("  issuer-proven halted member stock-days: 134/139")
print("  real independently sourced nominal-rights marks: 3")
print("  historical issuer ST 5% rule: one ticker/time interval")
print("  broker actual fills/historical Qlib factor vintages: NOT CERTIFIED")
print("Only source-derived metadata is committed to GitHub; raw results:", base)
PY
