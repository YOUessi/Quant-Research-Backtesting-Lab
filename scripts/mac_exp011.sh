#!/usr/bin/env bash
# EXP-011 fully offline: rehash/reparse 89 original issuer cash/right PDFs,
# then validate three independently archived unadjusted nominal share/cash
# examples through their ISSUER scheduled pay day. No credited broker cash,
# no model PnL, and never overwrite previous research outputs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Project .venv Python missing" >&2; exit 2; }
BASE="${1:-runs/exp011_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$BASE" ]] || { echo "Existing research output: $BASE" >&2; exit 2; }
CASH="data/pit/EXP005_issuer_cash_action_ledger_v3_20261027.json"
P19="data/pit/issuer_batch19_20261026/issuer_pdfs"
P30="data/pit/issuer_batch30_random_20261026/issuer_pdfs"
P0="data/pit/issuer_official_20261026/raw_official_pdfs"
VENDOR="data/pit/csi300_dynamic_2021_22_20261026"
QUOTES="data/pit/EXP007_additional_unadjusted_daily_quotes_20261027"
for path in "$CASH" "$P19" "$P30" "$P0" "$QUOTES"; do
    [[ -e "$path" ]] || { echo "Missing original source: $path" >&2; exit 2; }
done

"$PY" -m pytest -q
mkdir -p "$BASE"
"$PY" -m quant_lab.pit_share_distribution \
    --cash-ledger "$CASH" --issuer-pdfs "$P19" "$P30" "$P0" \
    --aggregator-dir "$VENDOR" --out "$BASE/rights.json"
"$PY" -m quant_lab.pit_capital_balance \
    --cash-ledger "$CASH" --share-audit "$BASE/rights.json" \
    --issuer-dirs "$P19" "$P30" "$P0" --out "$BASE/capital.json"
"$PY" -m quant_lab.pit_rights_catalog \
    --cash-ledger "$CASH" --share-audit "$BASE/rights.json" \
    --capital-proof "$BASE/capital.json" --out "$BASE/catalog.json"
"$PY" -m quant_lab.pit_receivable_due_audit \
    --rights-catalog "$BASE/catalog.json" \
    --original-pdfs "$P19" "$P30" "$P0" \
    --raw-quote-dir "$QUOTES" --out "$BASE/audit.json"
"$PY" - "$BASE/audit.json" <<'PY'
import json,sys
from decimal import Decimal
from pathlib import Path
a=json.loads(Path(sys.argv[1]).read_text("utf-8"))
assert a["verified_original_issuer_PDF_and_quote_csv_cases"] == 3
assert a["issuer_complete_rights_unchanged"] == 27
assert a["issuer_incomplete_rights_unchanged"] == 62
for c in a["cases"]:
    assert c["issuer_schedule_reached_quotation_days"] >= 1
    assert Decimal(c["gross_pretax_cash_claim_cny"]) == Decimal(
        c["gross_pretax_claim_remaining_at_final_available_quote_day_cny"])
    assert c["cash_credited_to_spendable_balance_cny"] == "0"
    assert c["no_trades_no_model_return_adjustment"]
print("EXP011 PASSED: 3 source PDF+quote SHA pins, issuer terms/dates,")
print("  full 89 rights re-audit and 3 due-date gross-claim rows;")
print("  no broker cash receipts/fills or return corrections inferred.")
PY
