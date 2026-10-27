#!/usr/bin/env bash
# EXP019: negative evidence audit; always keep the 46 unresolved rights unresolved.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP019_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Mac CPU Python virtualenv missing" >&2; exit 2; }
BASE="${1:-runs/exp019_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
  echo "Refusing non-ignored or previously existing audit output" >&2; exit 2;
}
git check-ignore -q "$BASE/exp019/source_negative_audit.json" || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp019_unresolved_rights_negative.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m pytest -q tests \
  "$SRC/tests/test_exp016_issuer_no_stock_proof.py" \
  "$SRC/tests/test_exp017_no_share_capital_change.py" \
  "$SRC/tests/test_exp018_treasury_cash_only.py" \
  "$SRC/tests/test_exp019_unresolved_rights_negative.py"
QUANT_LAB_ROOT="$ROOT" EXP018_SOURCE_DIR="$SRC" \
  bash "$SRC/scripts/mac_exp018.sh" "$BASE/frozen_exp018"
"$PY" -m quant_lab.pit_exp019_unresolved_rights_negative \
  --parent-catalog "$BASE/frozen_exp018/exp018/rights_catalog_exp018.json" \
  --issuer-pdfs data/pit/issuer_batch19_20261026/issuer_pdfs \
                 data/pit/issuer_batch30_random_20261026/issuer_pdfs \
                 data/pit/issuer_official_20261026/raw_official_pdfs \
  --out-dir "$BASE/exp019"
"$PY" - "$BASE" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
parent=root/"frozen_exp018/exp018/rights_catalog_exp018.json"
auditpath=root/"exp019/source_negative_audit.json"
old=json.loads(parent.read_bytes())
audit=json.loads(auditpath.read_bytes())
assert hashlib.sha256(parent.read_bytes()).hexdigest()==audit["input_frozen_exp018_catalog_sha256"]
assert audit["original_issuer_pdf_full_sha256_checked"]==89
assert (audit["previous_complete_share_rights"],audit["unresolved_share_rights"])==(43,46)
assert audit["historical_stability_not_post_distribution_proof"]==13
assert audit["other_unresolved_records"]==33
assert audit["newly_certified_complete_rights"]==0
assert audit["new_derived_rights_catalog_written"] is False
assert not any(audit[k] for k in ("broker_receipts_or_actual_fills_certified",
                                 "vintage_factors_or_daily_limit_prices_certified",
                                 "original_inputs_or_old_outputs_modified"))
rows=audit["unresolved_original_issuer_sources"]
assert len(rows)==46
keys={(r["symbol"],r["ex_date"]) for r in rows}
assert len(keys)==46
parent_unknown={(r["symbol"],r["ex_date"]) for r in old["events"]
                if not r["complete_rights_supported_by_issuer_original"]}
assert keys==parent_unknown
assert not (root/"exp019/rights_catalog_exp019.json").exists()
for r in rows:
    assert r["current_rights_issuance_certified"] is False
    assert r["zero_bonus_certified_by_this_audit"] is False
    assert r["zero_transfer_certified_by_this_audit"] is False
print("EXP019 VERIFIED: 89 full original issuer SHA256; 46 remain unresolved.")
print("13 pre-implementation lookback stability statements NOT promoted; 33 other holds.")
print("AUDIT_SHA256",hashlib.sha256(auditpath.read_bytes()).hexdigest())
PY
