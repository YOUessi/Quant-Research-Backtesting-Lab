#!/usr/bin/env bash
# EXP-006: offline CPU reproducibility for issuer share rights, frozen orders,
# factor alignment and nominal cash/stock rights. Never overwrites prior data.
set -euo pipefail

if [[ -n "$(printenv QUANT_LAB_ROOT || true)" ]]; then
  ROOT="$(printenv QUANT_LAB_ROOT)"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"
PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Requires isolated Python 3.10+ environment: install -e '.[test,ml,qlib,audit]'." >&2
  exit 2
fi

PIT="data/pit"
QLIB="runs/exp002_data_20261026_v1/dynamic_history.parquet"
FROZEN="runs/exp002_sim_20261026_v1"
ISSUER_BATCH_19="$PIT/issuer_batch19_20261026/issuer_pdfs"
ISSUER_BATCH_30="$PIT/issuer_batch30_random_20261026/issuer_pdfs"
PILOT="$PIT/issuer_official_20261026"
QUOTE="$PIT/EXP006_SZ300751_original_unadjusted_quote_20261027"
CASH="$PIT/EXP005_issuer_cash_action_ledger_v3_20261027.json"
RIGHTS_HALT="$PIT/EXP005_rights_issue_halts_20261027.json"
for FILE in "$CASH" "$QLIB" "$RIGHTS_HALT" \
            "$QUOTE/2022_daily_unadjusted.csv" "$QUOTE/2022_source.json" \
            "$PILOT/primary_evidence_report.json"; do
  if [[ ! -f "$FILE" ]]; then
    echo "Verified local evidence missing: $FILE" >&2
    echo "Never silently substitute synthetic bars, or future-filled closes." >&2
    exit 2
  fi
done

if [[ -n "$(printenv EXTRA_TEST_DIR || true)" ]]; then
  "$PY" -m pytest -q --import-mode=importlib tests "$(printenv EXTRA_TEST_DIR)"
else
  "$PY" -m pytest -q
fi

if [[ $# -gt 0 ]]; then
  BASE="$1"
else
  BASE="runs/exp006_$(date -u +%Y%m%dT%H%M%SZ)"
fi
if [[ -e "$BASE" ]]; then
  echo "Won't overwrite existing prior research output: $BASE" >&2
  exit 2
fi
mkdir -p "$BASE"

"$PY" -m quant_lab.pit_share_distribution \
  --cash-ledger "$CASH" \
  --issuer-pdfs "$ISSUER_BATCH_19" "$ISSUER_BATCH_30" "$PILOT/raw_official_pdfs" \
  --aggregator-dir "$PIT/csi300_dynamic_2021_22_20261026" \
  --out "$BASE/source_issuer_stock_rights.json"

"$PY" -m quant_lab.pit_order_corroboration \
  --frozen-execution "$FROZEN" \
  --rights-halt "$RIGHTS_HALT" \
  --original-primary-pdfs-report "$PILOT/primary_evidence_report.json" \
  --exchange-calendar data/external/qlib_20261025/calendars/day.txt \
  --out "$BASE/unchanged_old_frozen_order_audit.json"

"$PY" -m quant_lab.pit_positive_nominal_probe \
  --cash-ledger "$CASH" \
  --share-audit "$BASE/source_issuer_stock_rights.json" \
  --raw-bars "$QUOTE/2022_daily_unadjusted.csv" \
  --raw-source-meta "$QUOTE/2022_source.json" \
  --out "$BASE/nominal_unadjusted_priced_example"

"$PY" -m quant_lab.pit_factor_event_crosscheck \
  --cash-ledger "$CASH" \
  --share-audit "$BASE/source_issuer_stock_rights.json" \
  --qlib-parquet "$QLIB" \
  --raw-bars "$QUOTE/2022_daily_unadjusted.csv" \
  --raw-source "$QUOTE/2022_source.json" \
  --out "$BASE/vendor_adjustment_factor_crosscheck.json"

"$PY" - "$BASE" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
rights=json.loads((p/"source_issuer_stock_rights.json").read_text())
order=json.loads((p/"unchanged_old_frozen_order_audit.json").read_text())
nom=json.loads((p/"nominal_unadjusted_priced_example"/"EXP006_nominal_verified_transfer.json").read_text())
factor=json.loads((p/"vendor_adjustment_factor_crosscheck.json").read_text())
assert rights["n_verified_original_cash_events"]==89
assert order["distinct_issuer_original_PDF_halt_stock_session_keys"]==40
assert nom["nominal_shares_after_ex"]==1600
assert nom["pretax_cash_receivable"]==1500
assert factor["factor_arithmetic_consistent_with_simple_corporate_formula_within_0_05pct"]
assert not factor["historical_decision_day_adjustment_factor_version_proven"]
print("AUDIT ONLY: 89 issuer events, 40 halted stock-session keys, 1000->1600 shares,"
      " CNY1500 gross cash, vendor factor arithmetic consistent but PIT not certified.")
print("Results are gitignored:",p)
PY
