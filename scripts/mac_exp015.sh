#!/usr/bin/env bash
# EXP015: original 89-PDF SHA source-clock audit with exact Qlib calendar.
# Mac CPU only. All outputs gitignored and immutable; no trading or raw mutation.
set -euo pipefail
ROOT="${QUANT_LAB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "Missing Mac CPU virtualenv" >&2; exit 2; }
BASE="${1:-runs/exp015_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$BASE" == runs/* ]] || { echo "Output must be under gitignored runs/" >&2; exit 2; }
[[ ! -e "$BASE" ]] || { echo "Refusing prior run overwrite: $BASE" >&2; exit 2; }
git check-ignore -q "$BASE/source_audit.json" || { echo "Output is not gitignored" >&2; exit 2; }
if [[ -n "${EXP015_ISOLATED_SOURCE_DIR:-}" ]]; then
  M15="$EXP015_ISOLATED_SOURCE_DIR"
  M14="${EXP014_ISOLATED_SOURCE_DIR:-runs/exp014_source_mirror_20261027}"
  [[ "$M15" == runs/* && "$M14" == runs/* ]] || exit 2
  [[ -f "$M15/src/quant_lab/pit_rights_publication_gate.py" ]] || exit 2
  [[ -f "$M14/src/quant_lab/pit_exp014_rights_completion.py" ]] || exit 2
  export PYTHONPATH="$ROOT/$M15/src:$ROOT/$M14/src:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
  "$PY" -m pytest -q tests "$M14/tests" "$M15/tests"
  QUANT_LAB_ROOT="$ROOT" EXP014_ISOLATED_SOURCE_DIR="$M14" \
    bash "$M14/scripts/mac_exp014.sh" "$BASE/frozen_exp014"
else
  "$PY" -m pytest -q tests
  bash scripts/mac_exp014.sh "$BASE/frozen_exp014"
fi
P19="data/pit/issuer_batch19_20261026/issuer_pdfs"
P30="data/pit/issuer_batch30_random_20261026/issuer_pdfs"
P0="data/pit/issuer_official_20261026/raw_official_pdfs"
CAL="data/external/qlib_20261025/calendars/day.txt"
for path in "$P19" "$P30" "$P0" "$CAL"; do
  [[ -e "$path" ]] || { echo "Original issuer/calendar source missing: $path" >&2; exit 2; }
done
"$PY" -m quant_lab.pit_rights_publication_gate \
  --catalog "$BASE/frozen_exp014/exp014_new_proofs/rights_catalog_exp014.json" \
  --calendar "$CAL" --issuer-pdfs "$P19" "$P30" "$P0" \
  --out "$BASE/issuer_rights_source_clock_full.json"
"$PY" - "$BASE" <<'PY'
from pathlib import Path
import hashlib
import json
import sys
base=Path(sys.argv[1])
p=base/"issuer_rights_source_clock_full.json"
data=json.loads(p.read_text("utf-8"))
assert data["original_issuer_pdfs_full_SHA256_rechecked"] == 89
assert data["first_page_A_stock_issuer_identity_checked"] == 89
assert data["events_exact_next_session_publication_embargo_verified"] == 89
assert data["publication_time_decision_probes_checked"] == 267
assert (data["source_rights_complete"],data["source_rights_still_incomplete"]) == (36,53)
assert data["all_pre_publication_probes_censored"]
assert data["unresolved_rights_after_publication_still_censored"]
assert data["new_completed_issuer_events"] == 0
assert not data["original_intraday_publication_times_proven"]
assert not data["authoritative_issuer_revision_history_proven"]
assert not data["broker_cash_stock_credit_or_actual_orders_proven"]
assert not data["official_daily_limit_prices_or_auction_queues_proven"]
unknown=[]
for row in data["events"]:
    probes=row["source_day_decision_probes"]
    assert not probes[0]["issuer_pdf_known_from_day_only_notice_asof"]
    assert probes[1]["issuer_pdf_known_from_day_only_notice_asof"]
    assert not any(q["actual_cash_credit_proven"] or q["price_limit_and_auction_fill_proven"]
                   for q in probes)
    if not row["issuer_stock_rights_complete"]:
        unknown.append({
            "symbol":row["symbol"], "event_id":row["event_id"],
            "ex_date":row["original_ex_day"],
            "issuer_pdf_sha256":row["original_issuer_pdf_sha256"],
            "issuer_original_pdf_url":row["original_issuer_pdf_url"],
            "first_usable_exchange_day":row["first_usable_exchange_day"],
            "missing_bonus":row["bonus_rights_missing"],
            "missing_capital_transfer":row["capital_transfer_rights_missing"],
            "actual_broker_credit_or_execution_verified":False,
        })
assert len(unknown)==53
unknown.sort(key=lambda x: (int(x["missing_bonus"])+int(x["missing_capital_transfer"]),
                             x["ex_date"],x["symbol"]))
summary={
    "kind":"EXP015_SOURCE_CLOCK_AND_UNRESOLVED_RIGHTS_QUEUE",
    "research_date":"2026-10-27",
    "full_local_audit_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
    "catalog_full_sha256":data["catalog_original_full_sha256"],
    "historical_qlib_calendar_sha256":data["historical_qlib_exchange_calendar_full_sha256"],
    "issuer_original_full_byte_sha256_rechecked":89,
    "source_pdf_first_page_identity_rechecked":89,
    "source_first_usable_next_exchange_day_matched":89,
    "publication_decision_probes":267,
    "complete_stock_rights_events":36,
    "stock_rights_still_unresolved":53,
    "unresolved_missing_both_categories":data["unresolved_missing_both_categories"],
    "unresolved_missing_one_category":data["unresolved_missing_one_category"],
    "new_stock_rights_proofs_this_round":0,
    "source_pubtime_intradaily_verified":False,
    "issuer_amendment_history_verified":False,
    "broker_credit_price_limit_order_queue_verified":False,
    "actual_tradable_returns_verified":False,
    "unresolved_events":unknown,
}
(base/"source_clock_public_summary.json").write_text(
    json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"
)
print("EXP015 VERIFIED: 89 SHA+first page; 89 original notice-to-next-Qlib-session dates;")
print("  267 conservative time probes, 36 complete, 53 still CENSORED;")
print("  no original data changes, intraday/broker/factor/amendment proof or trading PnL.")
print("  public sanitized summary:",base/"source_clock_public_summary.json")
PY
