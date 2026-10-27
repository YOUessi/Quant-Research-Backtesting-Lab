#!/usr/bin/env bash
# EXP021: earlier issuer no-bonus plan + approved current implementation.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP021_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Mac CPU .venv not found" >&2; exit 2; }
BASE="${1:-runs/exp021_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
  echo "Refusing overwrite of prior results or nonignored output" >&2; exit 2;
}
git check-ignore -q "$BASE/exp021/source_audit.json" || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp021_cross_notice_bonus.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m pytest -q tests \
  "$SRC/tests/test_exp016_issuer_no_stock_proof.py" \
  "$SRC/tests/test_exp017_no_share_capital_change.py" \
  "$SRC/tests/test_exp018_treasury_cash_only.py" \
  "$SRC/tests/test_exp019_unresolved_rights_negative.py" \
  "$SRC/tests/test_exp020_issuer_identity_gate.py" \
  "$SRC/tests/test_exp021_cross_notice_bonus.py"
QUANT_LAB_ROOT="$ROOT" EXP020_SOURCE_DIR="$SRC" \
  bash "$SRC/scripts/mac_exp020.sh" "$BASE/frozen_exp020"
"$PY" -m quant_lab.pit_exp021_cross_notice_bonus \
  --parent-catalog "$BASE/frozen_exp020/frozen_exp019/frozen_exp018/exp018/rights_catalog_exp018.json" \
  --issuer-pdfs data/pit/issuer_batch19_20261026/issuer_pdfs \
                 data/pit/issuer_batch30_random_20261026/issuer_pdfs \
                 data/pit/issuer_official_20261026/raw_official_pdfs \
  --quarterly-original-pdf data/pit/exp021_exchange_original_20261028/SZ300751_20210428_Q1_source.pdf \
  --out-dir "$BASE/exp021"
"$PY" - "$BASE" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1])
parent=root/"frozen_exp020/frozen_exp019/frozen_exp018/exp018/rights_catalog_exp018.json"
child=root/"exp021/rights_catalog_exp021.json"
auditpath=root/"exp021/source_audit.json"
old=json.loads(parent.read_bytes())
new=json.loads(child.read_bytes())
audit=json.loads(auditpath.read_bytes())
assert hashlib.sha256(parent.read_bytes()).hexdigest()==audit["frozen_exp018_catalog_full_sha256"]
assert hashlib.sha256(child.read_bytes()).hexdigest()==audit["derived_exp021_catalog_full_sha256"]
assert audit["primary_issuer_original_full_sha256s_verified"]==89
assert audit["additional_full_original_quarterly_pdf_sha256_verified"]==1
assert audit["before_complete_unresolved"]==[43,46]
assert audit["after_complete_unresolved"]==[44,45]
assert audit["previously_unknown_bonus_fields_resolved"]==1
assert audit["other_event_rows_fully_unchanged"]==88
assert len(old["events"])==len(new["events"])==89
a={(r["symbol"],r["ex_date"]):r for r in old["events"]}
b={(r["symbol"],r["ex_date"]):r for r in new["events"]}
assert a.keys()==b.keys()
target=("SZ300751","2021-05-18")
for key in a:
    previous,post=a[key],b[key]
    if key==target:
        assert previous["bonus_shares_per_old_share"] is None
        assert previous["capital_transfer_shares_per_old_share"]==post["capital_transfer_shares_per_old_share"]==0.8
        assert (post["bonus_shares_per_old_share"],post["full_new_nominal_share_multiplier"])==(0.,1.8)
        assert post["complete_rights_supported_by_issuer_original"] is True
    else:
        assert previous==post,key
    for field in ("issuer_original_pdf_sha256","issuer_original_pdf_url",
                  "announcement_day","earliest_usable_exchange_day","record_date",
                  "ex_date","scheduled_cash_payment_day","gross_cash_per_old_nominal_share",
                  "broker_share_delivery_and_cash_payment_verified",
                  "original_publication_intraday_time_certified",
                  "historical_factor_vintage_available"):
        assert previous[field]==post[field],(key,field)
assert not any(audit[k] for k in (
    "original_pdfs_prior_catalogs_or_frozen_returns_modified",
    "actual_broker_shares_cash_credit_or_execution_proven",
    "as_published_factor_and_amendment_chain_proven"))
print("EXP021 VALIDATED: 89 pinned implementation PDF originals and one original earlier issuer quarterly report.")
print("RIGHTS: 43/46 => 44/45; 88 event rows unchanged, one missing bonus=0 sourced.")
print("CATALOG_SHA256:",hashlib.sha256(child.read_bytes()).hexdigest())
print("AUDIT_SHA256:",hashlib.sha256(auditpath.read_bytes()).hexdigest())
PY
