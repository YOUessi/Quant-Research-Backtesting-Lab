#!/usr/bin/env bash
# EXP013 additive original-issuer proof: five specifically pinned "only cash,
# no bonus/capital transfer" implementation statements. Offline Mac CPU only.
# Preserve the EXP012 frozen 27/62 replay and all original PDFs/quotes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Missing macOS .venv Python" >&2; exit 2; }
BASE="${1:-runs/exp013_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$BASE" ]] || { echo "Refusing to replace earlier output: $BASE" >&2; exit 2; }
P19="data/pit/issuer_batch19_20261026/issuer_pdfs"
P30="data/pit/issuer_batch30_random_20261026/issuer_pdfs"
P0="data/pit/issuer_official_20261026/raw_official_pdfs"
for d in "$P19" "$P30" "$P0"; do
    [[ -d "$d" ]] || { echo "Missing archived original issuer PDFs: $d" >&2; exit 2; }
done

# The previously published 27/62 evidence remains replayable, unchanged.
bash scripts/mac_exp012.sh "$BASE/frozen_exp012"
"$PY" -m quant_lab.pit_cash_only_original_completion \
    --baseline-catalog "$BASE/frozen_exp012/catalog.json" \
    --issuer-pdfs "$P19" "$P30" "$P0" \
    --out-dir "$BASE/exp013_new_proofs"

"$PY" - "$BASE/exp013_new_proofs" "$BASE/frozen_exp012/catalog.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root, prior = Path(sys.argv[1]), Path(sys.argv[2])
audit = json.loads((root/"source_audit.json").read_text("utf-8"))
new_bytes = (root/"rights_catalog_exp013.json").read_bytes()
cat = json.loads(new_bytes)
assert audit["baseline_catalog_full_sha256"] == hashlib.sha256(prior.read_bytes()).hexdigest()
assert audit["derived_catalog_full_sha256"] == hashlib.sha256(new_bytes).hexdigest()
assert audit["rehashed_original_issuer_PDF_events"] == 89
assert audit["before_complete_and_unresolved"] == [27, 62]
assert audit["after_complete_and_unresolved"] == [32, 57]
assert audit["newly_direct_current_issuer_verified_zero_bonus_and_transfer"] == 5
assert (cat["fully_verified_nominal_share_rights"], cat["unknown_share_rights"]) == (32, 57)
expected = {
    ("SH600703", "2022-07-14"), ("SH600705", "2021-08-05"),
    ("SH600705", "2022-07-07"), ("SH601318", "2022-06-20"),
    ("SH601318", "2022-10-20"),
}
proofs = {(p["symbol"], p["ex_date"]): p for p in audit["source_proofs"]}
assert set(proofs) == expected
before = {(x["symbol"], x["ex_date"]): x for x in json.loads(prior.read_text())["events"]}
after = {(x["symbol"], x["ex_date"]): x for x in cat["events"]}
assert set(before) == set(after)
for key in after:
    row = after[key]
    old = before[key]
    if key in expected:
        assert not old["complete_rights_supported_by_issuer_original"]
        assert row["complete_rights_supported_by_issuer_original"]
        assert row["bonus_shares_per_old_share"] == 0.0
        assert row["capital_transfer_shares_per_old_share"] == 0.0
        assert row["exp013_additional_direct_current_issuer_pdf_proof"] == proofs[key]
    else:
        assert row == old
    assert row["gross_cash_per_old_nominal_share"] == old["gross_cash_per_old_nominal_share"]
    assert row["earliest_usable_exchange_day"] == old["earliest_usable_exchange_day"]
    assert row["broker_share_delivery_and_cash_payment_verified"] is False
assert audit["historical_factor_versions_or_broker_credits_verified"] is False
assert audit["actual_portfolio_orders_or_returns_recomputed"] is False
print("EXP013 OFFLINE SOURCE PASS: 89 full-PDF SHA bytes rechecked;")
print("  5 original issuer direct CURRENT cash-only rights recovered;")
print("  separate 27/62 frozen base retained; derivative 32 complete / 57 unknown;")
print("  unchanged prior events, no assumed broker share/cash credit or trades.")
PY
