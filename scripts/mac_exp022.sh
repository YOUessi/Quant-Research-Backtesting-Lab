#!/usr/bin/env bash
# EXP022 original-issuer approved no-capitalization chain (partial transfer only).
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP022_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Mac CPU .venv absent" >&2; exit 2; }
BASE="${1:-runs/exp022_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
    echo "Refusing overwrite or non-ignored output" >&2; exit 2;
}
git check-ignore -q "$BASE/exp022/source_audit.json" || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp022_issuer_approved_partial_transfer.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m pytest -q tests \
    "$SRC/tests/test_exp016_issuer_no_stock_proof.py" \
    "$SRC/tests/test_exp017_no_share_capital_change.py" \
    "$SRC/tests/test_exp018_treasury_cash_only.py" \
    "$SRC/tests/test_exp019_unresolved_rights_negative.py" \
    "$SRC/tests/test_exp020_issuer_identity_gate.py" \
    "$SRC/tests/test_exp021_cross_notice_bonus.py" \
    "$SRC/tests/test_exp022_issuer_approved_partial_transfer.py"
QUANT_LAB_ROOT="$ROOT" EXP021_SOURCE_DIR="$SRC" \
    bash "$SRC/scripts/mac_exp021.sh" "$BASE/frozen_exp021"
"$PY" -m quant_lab.pit_exp022_issuer_approved_partial_transfer \
    --parent-catalog "$BASE/frozen_exp021/exp021/rights_catalog_exp021.json" \
    --issuer-pdfs data/pit/issuer_batch19_20261026/issuer_pdfs \
                   data/pit/issuer_batch30_random_20261026/issuer_pdfs \
                   data/pit/issuer_official_20261026/raw_official_pdfs \
    --issuer-original-folder data/pit/exp022_exchange_original_20261028 \
    --out-dir "$BASE/exp022"
"$PY" - "$BASE" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1])
old_path=root/"frozen_exp021/exp021/rights_catalog_exp021.json"
new_path=root/"exp022/rights_catalog_exp022.json"
audit_path=root/"exp022/source_audit.json"
before=json.loads(old_path.read_bytes())
after=json.loads(new_path.read_bytes())
audit=json.loads(audit_path.read_bytes())
assert hashlib.sha256(old_path.read_bytes()).hexdigest()==audit["frozen_exp021_source_catalog_full_sha256"]
assert hashlib.sha256(new_path.read_bytes()).hexdigest()==audit["new_derived_exp022_catalog_full_sha256"]
assert audit["primary_issuer_original_full_sha256_checked"]==89
assert audit["additional_issuer_hosted_original_full_sha256_checked"]==6
assert audit["fully_source_verified_rights_before_after"]==[44,44]
assert audit["unresolved_bonus_or_share_rights_before_after"]==[45,45]
assert audit["issuer_approved_capital_transfer_zero_newly_resolved"]==2
assert audit["other_event_rows_fully_unchanged"]==87
assert len(before["events"])==len(after["events"])==89
a={(r["symbol"],r["ex_date"]):r for r in before["events"]}
b={(r["symbol"],r["ex_date"]):r for r in after["events"]}
assert a.keys()==b.keys()
targets={("SH600015","2021-07-09"),("SH600015","2022-06-08")}
for key in a:
    x,y=a[key],b[key]
    if key in targets:
        assert x["capital_transfer_shares_per_old_share"] is None
        assert y["capital_transfer_shares_per_old_share"]==0.
        assert x["bonus_shares_per_old_share"] is y["bonus_shares_per_old_share"] is None
        assert x["full_new_nominal_share_multiplier"] is y["full_new_nominal_share_multiplier"] is None
        assert x["complete_rights_supported_by_issuer_original"] is y["complete_rights_supported_by_issuer_original"] is False
    else:
        assert x==y,key
    for f in ("issuer_original_pdf_sha256","issuer_original_pdf_url",
              "announcement_day","earliest_usable_exchange_day",
              "record_date","ex_date","scheduled_cash_payment_day",
              "gross_cash_per_old_nominal_share",
              "broker_share_delivery_and_cash_payment_verified",
              "historical_factor_vintage_available",
              "original_publication_intraday_time_certified"):
        assert x[f]==y[f],(key,f)
assert not audit["legacy_cash_publication_broker_and_model_data_modified"]
assert not audit["actual_broker_delivery_or_auction_fill_proven"]
assert not audit["historical_factor_vintage_or_complete_amendment_chain_proven"]
print("EXP022 original issuer sources 89 archived + 6 issuer-hosted PDFs whole-byte SHA verified.")
print("Share-right completion remains 44/45; two exact SH600015 transfer fields now 0, bonuses still unknown.")
print("DERIVED_CATALOG_SHA256",hashlib.sha256(new_path.read_bytes()).hexdigest())
print("PUBLIC_AUDIT_SHA256",hashlib.sha256(audit_path.read_bytes()).hexdigest())
PY
