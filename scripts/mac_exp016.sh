#!/usr/bin/env bash
# EXP016 exact 2-issuer-no-stock original-PDF replay; parent 89-event sources immutable.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP016_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Missing Mac CPU venv" >&2; exit 2; }
BASE="${1:-runs/exp016_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || { echo "Refuse non-ignored or existing run" >&2; exit 2; }
git check-ignore -q "$BASE/exp016/source_audit.json" || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp016_issuer_no_stock_proof.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$SRC" == "$ROOT" ]]; then
    "$PY" -m pytest -q tests
else
    "$PY" -m pytest -q tests "$SRC/tests/test_exp016_issuer_no_stock_proof.py"
fi
bash scripts/mac_exp015.sh "$BASE/frozen_exp015"
P19=data/pit/issuer_batch19_20261026/issuer_pdfs
P30=data/pit/issuer_batch30_random_20261026/issuer_pdfs
P0=data/pit/issuer_official_20261026/raw_official_pdfs
"$PY" -m quant_lab.pit_exp016_issuer_no_stock_proof \
    --baseline-catalog "$BASE/frozen_exp015/frozen_exp014/exp014_new_proofs/rights_catalog_exp014.json" \
    --issuer-pdfs "$P19" "$P30" "$P0" --out-dir "$BASE/exp016"
"$PY" - "$BASE" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); previous=json.loads((root/"frozen_exp015/frozen_exp014/exp014_new_proofs/rights_catalog_exp014.json").read_text())
newfile=root/"exp016/rights_catalog_exp016.json"
now=json.loads(newfile.read_text()); audit=json.loads((root/"exp016/source_audit.json").read_text())
assert hashlib.sha256(newfile.read_bytes()).hexdigest()==audit["derived_exp016_full_sha256"]
assert audit["original_event_pdf_sha256s_rechecked"]==89
assert (audit["direct_current_issuer_proofs"],audit["new_zero_share_categories"])==(2,4)
assert (audit["before_complete_unresolved"],audit["after_complete_unresolved"])==([36,53],[38,51])
assert (now["fully_verified_nominal_share_rights"],now["unknown_share_rights"])==(38,51)
keys={("SH600887","2021-06-11"),("SH600887","2022-06-01")}
a={(x["symbol"],x["ex_date"]):x for x in previous["events"]}
b={(x["symbol"],x["ex_date"]):x for x in now["events"]}
assert len(a)==len(b)==89 and a.keys()==b.keys()
for key in a:
    before,after=a[key],b[key]
    if key in keys:
        assert not before["complete_rights_supported_by_issuer_original"]
        assert after["complete_rights_supported_by_issuer_original"]
        assert (after["bonus_shares_per_old_share"],after["capital_transfer_shares_per_old_share"])==(0.,0.)
        assert after["full_new_nominal_share_multiplier"]==1.
    else:
        assert before==after, key
    for field in ("announcement_day","earliest_usable_exchange_day","record_date","ex_date",
                  "scheduled_cash_payment_day","gross_cash_per_old_nominal_share",
                  "issuer_original_pdf_url","issuer_original_pdf_sha256",
                  "broker_share_delivery_and_cash_payment_verified"):
        assert before[field]==after[field],(key,field)
assert not any(audit[k] for k in (
    "original_pdf_new_downloads","original_or_prior_catalog_mutation",
    "broker_credit_or_saleable_shares_proven","official_daily_price_limit_or_auction_fills_proven",
    "historical_portfolio_returns_validated","independent_historical_factor_vintage_proven"))
print("EXP016 VERIFIED: 89 original SHA; 2 direct current PDF proofs; 36/53 -> 38/51;")
print("frozen parent and 87 non-target issuer rows unchanged; broker/market PnL BLOCK")
PY
