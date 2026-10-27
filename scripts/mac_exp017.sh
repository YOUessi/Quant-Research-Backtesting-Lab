#!/usr/bin/env bash
# EXP017: original issuer cash-only/no-share-capital-change proof, Mac CPU.
# Source: exact GitHub EXP016 detached SHA worktree if primary checkout diverges.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SRC="${EXP017_SOURCE_DIR:-$ROOT}"
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Mac CPU venv missing" >&2; exit 2; }
BASE="${1:-runs/exp017_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
    echo "Refusing to overwrite existing/non-gitignored evidence output" >&2; exit 2;
}
git check-ignore -q "$BASE/exp017/source_audit.json" || {
    echo "Refusing to store audit outside gitignored runs/" >&2; exit 2;
}
[[ -f "$SRC/src/quant_lab/pit_exp017_no_share_capital_change.py" ]] || exit 2
[[ -f "$SRC/src/quant_lab/pit_exp016_issuer_no_stock_proof.py" ]] || exit 2
export PYTHONPATH="$SRC/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$SRC" == "$ROOT" ]]; then
    "$PY" -m pytest -q tests
else
    "$PY" -m pytest -q tests \
        "$SRC/tests/test_exp016_issuer_no_stock_proof.py" \
        "$SRC/tests/test_exp017_no_share_capital_change.py"
fi
# Replay all original source-gates from EXP012 through EXP016; no source mutation.
QUANT_LAB_ROOT="$ROOT" EXP016_SOURCE_DIR="$SRC" \
    bash "$SRC/scripts/mac_exp016.sh" "$BASE/frozen_exp016"
P19=data/pit/issuer_batch19_20261026/issuer_pdfs
P30=data/pit/issuer_batch30_random_20261026/issuer_pdfs
P0=data/pit/issuer_official_20261026/raw_official_pdfs
"$PY" -m quant_lab.pit_exp017_no_share_capital_change \
    --parent-catalog "$BASE/frozen_exp016/exp016/rights_catalog_exp016.json" \
    --issuer-pdfs "$P19" "$P30" "$P0" --out-dir "$BASE/exp017"
"$PY" - "$BASE" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
parent = root / "frozen_exp016/exp016/rights_catalog_exp016.json"
p = json.loads(parent.read_text())
newfile = root / "exp017/rights_catalog_exp017.json"
n = json.loads(newfile.read_text())
audit = json.loads((root / "exp017/source_audit.json").read_text())
assert hashlib.sha256(parent.read_bytes()).hexdigest() == audit["frozen_exp016_catalog_sha256"]
assert hashlib.sha256(newfile.read_bytes()).hexdigest() == audit["new_exp017_catalog_sha256"]
assert audit["archived_source_pdf_complete_sha256s_rechecked"] == 89
assert audit["current_issuer_original_direct_proofs"] == 2
assert audit["newly_filled_zero_categories"] == 4
assert (audit["old_complete_unknown"], audit["new_complete_unknown"]) == ([38, 51], [40, 49])
assert (n["fully_verified_nominal_share_rights"], n["unknown_share_rights"]) == (40, 49)
old = {(r["symbol"], r["ex_date"]):r for r in p["events"]}
new = {(r["symbol"], r["ex_date"]):r for r in n["events"]}
keys = {("SZ300142", "2021-05-19"), ("SZ300142", "2022-04-26")}
assert len(old) == len(new) == 89 and old.keys() == new.keys()
assert audit["other_original_event_rows_unchanged"] == 87
for key in old:
    before, after = old[key], new[key]
    if key in keys:
        assert not before["complete_rights_supported_by_issuer_original"]
        assert after["complete_rights_supported_by_issuer_original"]
        assert (after["bonus_shares_per_old_share"],
                after["capital_transfer_shares_per_old_share"],
                after["full_new_nominal_share_multiplier"]) == (0.,0.,1.)
    else:
        assert before == after, key
    for field in ("announcement_day", "earliest_usable_exchange_day",
                  "record_date", "ex_date", "scheduled_cash_payment_day",
                  "gross_cash_per_old_nominal_share", "issuer_original_pdf_url",
                  "issuer_original_pdf_sha256", "broker_share_delivery_and_cash_payment_verified"):
        assert before[field] == after[field], (key,field)
assert not any(audit[k] for k in (
    "original_pdfs_or_frozen_catalog_modified",
    "official_daily_limit_and_broker_order_fill_certified",
    "intraday_release_timestamps_certified",
    "actual_cash_or_new_stock_broker_credit_certified",
    "historical_asof_adjustment_factors_certified",
    "new_backtest_or_independent_returns_claimed"))
print("EXP017 VERIFIED: 89 archived issuer original full SHAs, two SZ300142")
print("current issuer no-share-capital-change proofs: 38/51 -> 40/49.")
print("Unmodified 87 non-target events, no broker posting/execution claims; FINANCE BLOCK.")
PY
