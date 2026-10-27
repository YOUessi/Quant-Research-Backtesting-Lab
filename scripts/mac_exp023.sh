#!/usr/bin/env bash
# EXP023 original issuer annual + approved AGM + final 2021–22 SPDB rights.
# Offline read-only source/hash checks and Mac CPU regression. No training.
set -euo pipefail

if [[ -n "$(printenv QUANT_LAB_ROOT || true)" ]]; then
  ROOT="$(printenv QUANT_LAB_ROOT)"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
if [[ -n "$(printenv EXP023_SOURCE_DIR || true)" ]]; then
  SRC="$(printenv EXP023_SOURCE_DIR)"
else
  SRC="$ROOT"
fi
cd "$ROOT"
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "Project Mac Python .venv absent" >&2; exit 2; }
[[ -f "$SRC/src/quant_lab/pit_exp023_spdb_approved_annual_zero.py" ]] || {
  echo "Exact EXP023 source missing" >&2; exit 2;
}
if [[ $# -gt 0 ]]; then BASE="$1"; else BASE="runs/exp023_$(date -u +%Y%m%dT%H%M%SZ)"; fi
[[ "$BASE" == runs/* && ! -e "$BASE" ]] || {
  echo "Refusing existing/outside ignored experiment output" >&2; exit 2;
}
git check-ignore -q "$BASE/exp023/source_audit.json" || {
  echo "Experiment output not Git-ignored" >&2; exit 2;
}
PARENT="runs/exp022_automation11_fresh_replay_20261028/exp022/rights_catalog_exp022.json"
PRIMARY="data/pit/exp023_spdb_original_20261028"
CALENDAR="data/external/qlib_20261025/calendars/day.txt"
for file in "$PARENT" "$CALENDAR" \
  "$PRIMARY/2021_2020_annual_original.pdf" \
  "$PRIMARY/2021_2020_board_profit.pdf" \
  "$PRIMARY/2021_2020_AGM_materials.pdf" \
  "$PRIMARY/2021_2020_AGM_resolution.pdf" \
  "$PRIMARY/2021_2020_implementation.pdf" \
  "$PRIMARY/2022_2021_annual_original.pdf" \
  "$PRIMARY/2022_2021_board_profit.pdf" \
  "$PRIMARY/2022_2021_AGM_materials.pdf" \
  "$PRIMARY/2022_2021_AGM_resolution.pdf" \
  "$PRIMARY/2022_2021_implementation.pdf"; do
  [[ -f "$file" ]] || {
    echo "Required issuer-original SHA-verifiable historical input missing: $file" >&2; exit 2;
  }
done
export PYTHONPATH="$SRC/src:$ROOT/src"

"$PY" -m pytest -q --import-mode=importlib "$SRC/tests"

"$PY" -m quant_lab.pit_exp023_spdb_approved_annual_zero \
  --parent-catalog "$PARENT" \
  --source-original-folder "$PRIMARY" \
  --archived-issuer-pdfs \
     data/pit/issuer_batch19_20261026/issuer_pdfs \
     data/pit/issuer_batch30_random_20261026/issuer_pdfs \
     data/pit/issuer_official_20261026/raw_official_pdfs \
  --exchange-calendar "$CALENDAR" \
  --out-dir "$BASE/exp023"

"$PY" - "$PARENT" "$BASE" <<'PY'
import hashlib,json,sys
from pathlib import Path
old=Path(sys.argv[1]); root=Path(sys.argv[2])/"exp023"
p=root/"rights_catalog_exp023.json"
a=root/"source_audit.json"
old_bytes=old.read_bytes(); child_bytes=p.read_bytes()
parent=json.loads(old_bytes); result=json.loads(child_bytes); audit=json.loads(a.read_bytes())
assert audit["parent_original_catalog_sha256"]==hashlib.sha256(old_bytes).hexdigest()
assert audit["derived_new_catalog_sha256"]==hashlib.sha256(child_bytes).hexdigest()
assert (audit["original_full_rights_before_after"],
        audit["original_unresolved_rights_before_after"])==([44,46],[45,43])
assert audit["original_issuer_implementation_PDFs_whole_sha256_verified"]==89
assert audit["additional_original_annual_approval_and_final_PDFs_verified"]==10
assert audit["source_table_zero_bonus_and_transfer_newly_complete"]==2
assert audit["other_source_event_rows_fully_unchanged"]==87
assert not audit["broker_cash_stock_credits_or_executable_trade_verified"]
assert not audit["historical_factor_vintage_or_all_amendment_chain_verified"]
oldby={x["event_id"]:x for x in parent["events"]}
newby={x["event_id"]:x for x in result["events"]}
assert oldby.keys()==newby.keys() and len(oldby)==89
changed=[k for k in oldby if oldby[k]!=newby[k]]
assert len(changed)==2
for k in changed:
    a,b=oldby[k],newby[k]
    assert a["symbol"]==b["symbol"]=="SH600000"
    assert a["gross_cash_per_old_nominal_share"]==b["gross_cash_per_old_nominal_share"]
    assert b["bonus_shares_per_old_share"]==b["capital_transfer_shares_per_old_share"]==0
    assert b["full_new_nominal_share_multiplier"]==1.0
    assert b["complete_rights_supported_by_issuer_original"]
for k in oldby:
    if k not in changed:assert oldby[k]==newby[k],k
print("EXP023 VERIFIED: 89 frozen issuer originals + 10 new original approval-chain PDFs.")
print("EXACT TWO events: SH600000 2021/2022 bonus=0, transfer=0; complete rights 44 -> 46.")
print("87 original event rows unchanged. No broker cash, fill or as-of factor vintages.")
print("CATALOG_SHA256",hashlib.sha256(child_bytes).hexdigest())
print("AUDIT_SHA256",hashlib.sha256(a.read_bytes()).hexdigest())
PY
