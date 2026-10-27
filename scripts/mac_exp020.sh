#!/usr/bin/env bash
# EXP020: primary A-stock first-page identity; no old output or trading modifications.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP020_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Missing authorized Mac CPU virtualenv" >&2; exit 2; }
BASE="${1:-runs/exp020_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
  echo "Refusing to overwrite existing or non-ignored source results" >&2; exit 2;
}
git check-ignore -q "$BASE/exp020/issuer_notice_identity_audit.json" || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp020_issuer_identity_gate.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m pytest -q tests \
  "$SRC/tests/test_exp016_issuer_no_stock_proof.py" \
  "$SRC/tests/test_exp017_no_share_capital_change.py" \
  "$SRC/tests/test_exp018_treasury_cash_only.py" \
  "$SRC/tests/test_exp019_unresolved_rights_negative.py" \
  "$SRC/tests/test_exp020_issuer_identity_gate.py"
QUANT_LAB_ROOT="$ROOT" EXP019_SOURCE_DIR="$SRC" \
  bash "$SRC/scripts/mac_exp019.sh" "$BASE/frozen_exp019"
"$PY" -m quant_lab.pit_exp020_issuer_identity_gate \
  --parent-catalog "$BASE/frozen_exp019/frozen_exp018/exp018/rights_catalog_exp018.json" \
  --issuer-pdfs data/pit/issuer_batch19_20261026/issuer_pdfs \
                 data/pit/issuer_batch30_random_20261026/issuer_pdfs \
                 data/pit/issuer_official_20261026/raw_official_pdfs \
  --out-dir "$BASE/exp020"
"$PY" - "$BASE" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
a=root/"exp020/issuer_notice_identity_audit.json"
catalog=root/"frozen_exp019/frozen_exp018/exp018/rights_catalog_exp018.json"
raw=catalog.read_bytes()
audit=json.loads(a.read_bytes())
parent=json.loads(raw)
assert hashlib.sha256(raw).hexdigest()==audit["input_frozen_exp018_catalog_sha256"]
assert (audit["full_original_pdf_sha256_checked"],audit["primary_stock_first_pages_verified"])==(89,89)
assert audit["header_type_counts"]=={
    "EXPLICIT_A_SHARE_STOCK_CODE":2,"SECURITY_CODE":83,"STOCK_CODE":4}
assert audit["first_page_notice_type_counts"]=={
    "CASH_DIVIDEND_IMPLEMENTATION":8,"EQUITY_DISTRIBUTION_IMPLEMENTATION":81}
assert (audit["complete_share_rights_unchanged"],audit["unresolved_share_rights_unchanged"])==(43,46)
assert audit["newly_proven_share_rights"]==0
assert len(audit["issuer_original_event_identity_audit"])==89
assert { (r["symbol"],r["ex_date"]) for r in audit["issuer_original_event_identity_audit"]} == {
    (r["symbol"],r["ex_date"]) for r in parent["events"] }
assert not any(audit[k] for k in (
    "broker_credit_or_executable_fills_proven",
    "historical_factor_vintages_proven","raw_source_or_prior_results_modified"))
print("EXP020 VERIFIED: 89 full original SHA256 + 89 primary A-stock headers; rights 43/46 unchanged.")
print("AUDIT_SHA256",hashlib.sha256(a.read_bytes()).hexdigest())
PY
