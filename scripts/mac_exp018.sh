#!/usr/bin/env bash
# EXP018 original issuer cash-only treasury exclusion: Mac CPU original source replay.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP018_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Mac CPU venv missing" >&2; exit 2; }
BASE="${1:-runs/exp018_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
    echo "Refusing to overwrite existing or non-ignored source output" >&2; exit 2;
}
git check-ignore -q "$BASE/exp018/source_audit.json" || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp018_treasury_cash_only.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$SRC" == "$ROOT" ]]; then
    "$PY" -m pytest -q tests
else
    "$PY" -m pytest -q tests \
        "$SRC/tests/test_exp016_issuer_no_stock_proof.py" \
        "$SRC/tests/test_exp017_no_share_capital_change.py" \
        "$SRC/tests/test_exp018_treasury_cash_only.py"
fi
QUANT_LAB_ROOT="$ROOT" EXP017_SOURCE_DIR="$SRC" \
    bash "$SRC/scripts/mac_exp017.sh" "$BASE/frozen_exp017"
P19=data/pit/issuer_batch19_20261026/issuer_pdfs
P30=data/pit/issuer_batch30_random_20261026/issuer_pdfs
P0=data/pit/issuer_official_20261026/raw_official_pdfs
"$PY" -m quant_lab.pit_exp018_treasury_cash_only \
    --parent-catalog "$BASE/frozen_exp017/exp017/rights_catalog_exp017.json" \
    --issuer-pdfs "$P19" "$P30" "$P0" --out-dir "$BASE/exp018"
"$PY" - "$BASE" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
oldfile=root/"frozen_exp017/exp017/rights_catalog_exp017.json"
newfile=root/"exp018/rights_catalog_exp018.json"
old=json.loads(oldfile.read_text())
new=json.loads(newfile.read_text())
audit=json.loads((root/"exp018/source_audit.json").read_text())
assert hashlib.sha256(oldfile.read_bytes()).hexdigest()==audit["input_frozen_exp017_catalog_sha256"]
assert hashlib.sha256(newfile.read_bytes()).hexdigest()==audit["derived_exp018_catalog_sha256"]
assert (old["fully_verified_nominal_share_rights"],old["unknown_share_rights"])==(40,49)
assert (new["fully_verified_nominal_share_rights"],new["unknown_share_rights"])==(43,46)
assert audit["original_issuer_pdf_full_sha256_checked"]==89
assert (audit["new_current_issuer_source_proofs"],audit["previous_unknown_to_zero_fields"])==(3,6)
a={(r["symbol"],r["ex_date"]):r for r in old["events"]}
b={(r["symbol"],r["ex_date"]):r for r in new["events"]}
keys={("SZ002311","2021-07-09"),("SZ002311","2022-07-07"),("SZ300760","2022-05-19")}
assert len(a)==len(b)==89 and a.keys()==b.keys()
assert audit["other_events_json_equal"]==86
for key in a:
    before,after=a[key],b[key]
    if key in keys:
        assert before["complete_rights_supported_by_issuer_original"] is False
        assert after["complete_rights_supported_by_issuer_original"] is True
        assert (after["bonus_shares_per_old_share"],
                after["capital_transfer_shares_per_old_share"],
                after["full_new_nominal_share_multiplier"])==(0.,0.,1.)
        proof=after["exp018_original_issuer_treasury_cash_proof"]
        assert proof["cash_reference_not_holder_cash_claim"] is True
        assert proof["actual_broker_cash_or_stock_credit_verified"] is False
    else:
        assert before==after,key
    for field in ("announcement_day","earliest_usable_exchange_day","record_date",
                  "ex_date","scheduled_cash_payment_day","gross_cash_per_old_nominal_share",
                  "issuer_original_pdf_sha256","issuer_original_pdf_url",
                  "broker_share_delivery_and_cash_payment_verified"):
        assert before[field]==after[field],(key,field)
assert audit["no_prior_pdf_or_catalog_overwrite"] is True
assert not any(audit[k] for k in (
    "broker_credit_or_execution_certified","published_vintage_factors_certified",
    "official_exchange_limit_price_certified","prior_frozen_returns_modified"))
print("EXP018 PASSED: 89 full original issuer PDFs, 3 direct treasury-cash-only proofs")
print("40/49 -> 43/46; 86 untouched event rows, no actual broker execution.")
PY
