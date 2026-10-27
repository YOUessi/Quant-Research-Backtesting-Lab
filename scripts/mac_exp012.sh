#!/usr/bin/env bash
# EXP-012: no numeric ex-day mark when issuer share terms are UNKNOWN.
# Replays issuer-PDF SHA-pinned 89-case catalog and 3 real-PDF/raw-CSV audits
# through the EXP011 offline runner. No original source or prior run overwrite.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Missing Mac project .venv" >&2; exit 2; }
BASE="${1:-runs/exp012_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$BASE" ]] || { echo "Refusing existing output: $BASE" >&2; exit 2; }

if [[ -n "${EXP012_EXTRA_TEST_DIR:-}" ]]; then
    "$PY" -m pytest -q tests "$EXP012_EXTRA_TEST_DIR"
else
    "$PY" -m pytest -q tests
fi

bash "$ROOT/scripts/mac_exp011.sh" "$BASE"

"$PY" - "$BASE/audit.json" <<'PY'
import json
import sys
from decimal import Decimal
from pathlib import Path

r=json.loads(Path(sys.argv[1]).read_text("utf-8"))
assert r["source_issuer_events_unchanged"] == 89
assert r["issuer_complete_rights_unchanged"] == 27
assert r["issuer_incomplete_rights_unchanged"] == 62
assert r["verified_original_issuer_PDF_and_quote_csv_cases"] == 3
expected={
    ("SH600276", "2021-06-10"): Decimal("200"),
    ("SH600760", "2021-06-24"): Decimal("400"),
    ("SH603392", "2022-04-21"): Decimal("450"),
}
assert len(r["cases"]) == 3
for case in r["cases"]:
    key=(case["symbol"], case["ex_date"])
    assert Decimal(case["ex_day_issuer_new_share_claim_uncredited"]) == expected[key]
    assert Decimal(case["ex_day_entitled_nominal_shares"]) == Decimal("1000")+expected[key]
    assert case["broker_confirmed_sellable_share_quantity"] is None
    assert case["broker_issued_share_credit_obtained"] is False
    assert case["cash_credited_to_spendable_balance_cny"] == "0"
    assert case["quoted_stock_rights_are_not_certified_sellable_new_shares"] is True
    assert case["no_trades_no_model_return_adjustment"] is True
print("EXP012 OFFLINE SOURCE PASS: 89 original issuer rights, 27 complete / 62 incomplete;")
print("  3 SHA-reverified PDF+raw CSV cases: 200/400/450 issuer new-share CLAIMS;")
print("  broker credited shares/sellable quantity UNKNOWN, NOT presumed zero or verified.")
PY
