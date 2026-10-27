#!/usr/bin/env bash
# EXP014: four new original issuer 2021/2022 cash-only/zero-share proofs.
# Offline Mac CPU; never amend frozen EXP012/013 source-derived catalogs.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Missing Mac local project virtualenv" >&2; exit 2; }
BASE="${1:-runs/exp014_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* ]] || { echo "Only gitignored runs/ output is allowed" >&2; exit 2; }
[[ ! -e "$BASE" ]] || { echo "Refusing to overwrite an existing run: $BASE" >&2; exit 2; }
git check-ignore -q "$BASE/example.json" || { echo "Refusing non-gitignored destination" >&2; exit 2; }

if [[ -n "${EXP014_ISOLATED_SOURCE_DIR:-}" ]]; then
  MIRROR="$EXP014_ISOLATED_SOURCE_DIR"
  [[ "$MIRROR" == runs/* ]] || { echo "Mirror must be inside gitignored runs/" >&2; exit 2; }
  [[ -f "$MIRROR/src/quant_lab/pit_exp014_rights_completion.py" ]] || exit 2
  export PYTHONPATH="$ROOT/$MIRROR/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
  "$PY" -m pytest -q tests "$MIRROR/tests"
else
  "$PY" -m pytest -q tests
fi

# Re-run the entire prior EXP013 original-source replay, which in turn
# replays EXP012's 89 issuer PDFs and three SHA-backed unadjusted quote cases.
bash scripts/mac_exp013.sh "$BASE/frozen_exp013"

P19="data/pit/issuer_batch19_20261026/issuer_pdfs"
P30="data/pit/issuer_batch30_random_20261026/issuer_pdfs"
P0="data/pit/issuer_official_20261026/raw_official_pdfs"
for d in "$P19" "$P30" "$P0"; do
  [[ -d "$d" ]] || { echo "Required original issuer PDFs absent: $d" >&2; exit 2; }
done

"$PY" -m quant_lab.pit_exp014_rights_completion \
  --baseline-catalog "$BASE/frozen_exp013/exp013_new_proofs/rights_catalog_exp013.json" \
  --issuer-pdfs "$P19" "$P30" "$P0" \
  --out-dir "$BASE/exp014_new_proofs"

"$PY" - "$BASE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

base = Path(sys.argv[1])
old = json.loads((base / "frozen_exp013/exp013_new_proofs/rights_catalog_exp013.json")
                 .read_text("utf-8"))
directory = base / "exp014_new_proofs"
new_bytes = (directory / "rights_catalog_exp014.json").read_bytes()
new = json.loads(new_bytes)
audit = json.loads((directory / "source_audit.json").read_text("utf-8"))
expected = {
    ("SH600276", "2022-07-05"),
    ("SH601225", "2021-07-09"),
    ("SZ300676", "2021-07-07"),
    ("SZ300676", "2022-07-06"),
}
assert audit["new_exp014_catalog_full_sha256"] == hashlib.sha256(new_bytes).hexdigest()
assert audit["original_issuer_pdf_event_hashes_rechecked"] == 89
assert audit["source_proofs_verified"] == 4
assert audit["newly_established_zero_stock_right_categories"] == 6
assert audit["old_completed_unknown"] == [32, 57]
assert audit["derived_completed_unknown"] == [36, 53]
assert (new["fully_verified_nominal_share_rights"],
        new["unknown_share_rights"]) == (36, 53)
proofs = {(p["symbol"], p["ex_date"]) for p in audit["source_proofs"]}
assert proofs == expected
previous = {(e["symbol"], e["ex_date"]): e for e in old["events"]}
after = {(e["symbol"], e["ex_date"]): e for e in new["events"]}
assert set(previous) == set(after) and len(after) == 89
for key, row in after.items():
    before = previous[key]
    if key in expected:
        assert not before["complete_rights_supported_by_issuer_original"]
        assert row["complete_rights_supported_by_issuer_original"]
        assert row["bonus_shares_per_old_share"] == 0.
        assert row["capital_transfer_shares_per_old_share"] == 0.
        assert row["full_new_nominal_share_multiplier"] == 1.
        assert row["broker_share_delivery_and_cash_payment_verified"] is False
    else:
        assert row == before, f"Unsupported changes to frozen non-target: {key}"
    for field in ("announcement_day", "earliest_usable_exchange_day",
                  "record_date", "ex_date", "scheduled_cash_payment_day",
                  "gross_cash_per_old_nominal_share", "issuer_original_pdf_sha256",
                  "issuer_original_pdf_url"):
        assert row[field] == before[field], (key, field)
assert audit["source_pdfs_newly_downloaded"] is False
assert audit["raw_source_documents_or_old_audits_mutated"] is False
assert audit["actual_broker_cash_or_share_postings_verified"] is False
assert audit["actual_trading_price_limits_auction_fills_or_returns_verified"] is False
print("EXP014 VERIFIED OFFLINE SOURCE: 89 issuer SHA bytes + four new current plan proofs;")
print("  Frozen original 27/62 and EXP013 32/57 still reproducible; new 36/53;")
print("  Six new stock-zero categories. Broker cash, sellable shares, fills unproved.")
PY
