"""EXP013: narrowly proved zero stock/transfer entitlements from original issuer text.

Additive overlay ONLY: EXP011/012's frozen 27/62 catalog and reproducibility
remain unchanged. Five newly confirmed direct, CURRENT implementation clauses
support two zero categories; no absence-of-mention or Qlib factor inference.
Only original issuer PDF bytes (full SHA256 pinned) are accepted.
No broker credit, shares availability, trades, taxes or returns are inferred.
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from pypdf import PdfReader

from .pit_official_batch import extract_explicit_pretax_cash_per_share
from .pit_original_date_recovery import issuer_implementation_dates
from .pit_share_distribution import clean, extract_share_terms

# Exact source identities independently re-read from the already archived
# original CNINFO issuer implementation PDFs. These are NOT vendor factors.
PINNED_NEW_SOURCE_IDS = {
    ("SH600703", "2022-07-14"): "ea47709e05fe1bddc5693fea5716766f5cfc8f7688dcec7414971b17fcb1c25f",
    ("SH600705", "2021-08-05"): "02e1a0bad42ae4ed00803c9d0df58df0e50a6ce268b0dc9ddced6e6d0daa65f7",
    ("SH600705", "2022-07-07"): "17250533a9f1da13fd3b51a2e1b19b4659300bcea42f60f3f2985fb328bd2295",
    ("SH601318", "2022-06-20"): "c3c7aa1b51962b1441c6d9a2cdafe6c66264323b2f4c39a2e9b30a6c180d0bd3",
    ("SH601318", "2022-10-20"): "63ba8885c1954203bd16dacb4368fd169e611b3b997756c9c702bf7a275782b8",
}
# Require BOTH actual-implementation cash-only declaration and the issuer's
# explicit unchanged circulating-stock ratio in the immediately ensuing text.
# Mere 'only cash' snippets, boilerplate and generic dividend formulae do not
# certify either of the absent stock-rights categories.
CURRENT_CASH_ONLY = re.compile(
    r"(?:本公司|公司)?本次仅进行现金红利分配[，,]?无送股和转增(?:分配|股份)?"
)
UNCHANGED_TRADABLE_SHARE_RATIO = re.compile(
    r"(?:本公司|公司)?流通股不会发生变化[，,]?流通股份变动比例为0"
)
SOURCE_GRADE = "DIRECT_CURRENT_IMPLEMENTATION_CASH_ONLY_BOTH_ZERO_EXP013"


def _decimal_eq(a, b) -> bool:
    return abs(Decimal(str(a)) - Decimal(str(b))) <= Decimal("0.000000001")


def current_issuer_cash_only_clause(source_text: str) -> bool:
    """Reject weak narratives; conflicts with numeric stock rights fail closed."""
    t = clean(source_text)
    matched = any(
        UNCHANGED_TRADABLE_SHARE_RATIO.search(t[m.end(): m.end() + 100])
        for m in CURRENT_CASH_ONLY.finditer(t)
    )
    if not matched:
        return False
    rights = extract_share_terms(source_text)
    if (rights["bonus_per_ten_distinct_candidates"]
        or rights["transfer_per_ten_distinct_candidates"]
        or rights["bonus_source_status"].startswith("CONFLICTING")
        or rights["transfer_source_status"].startswith("CONFLICTING")):
        raise ValueError("Numeric stock rights conflict with explicit current cash-only clause")
    return True


def verify_original_issuer_cash_only(event: dict, payload: bytes) -> dict | None:
    """Verify complete original bytes, issuer identity, dates, cash and both zeros."""
    original_hash = event["issuer_original_pdf_sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", original_hash):
        raise ValueError("Original issuer PDF full SHA256 missing")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != original_hash:
        raise ValueError("Original issuer PDF SHA256 mismatch")
    if not payload.startswith(b"%PDF"):
        raise ValueError("Original issuer source is not a PDF")
    if not str(event.get("issuer_original_pdf_url", "")).startswith(
            "https://static.cninfo.com.cn/finalpage/"):
        raise ValueError("Original issuer domain gate failed")
    reader = PdfReader(BytesIO(payload), strict=False)
    if not reader.pages:
        raise ValueError("Issuer PDF has no readable pages")
    first_page = reader.pages[0].extract_text() or ""
    symbol = event["symbol"]
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:5])
    # All 89 frozen originals get SHA-verified and scanned. The narrower
    # implementation-title/header requirement applies only to new claims;
    # other original PDF formats are not invalidated by this supplement.
    if not current_issuer_cash_only_clause(text):
        return None
    header = clean(first_page)
    if (symbol[2:] not in header
        or not any(title in header for title in (
            "权益分派实施公告", "利润分配实施公告", "分红派息实施公告"))):
        raise ValueError("Primary A-stock identifier or implementation title absent")
    key = (symbol, event["ex_date"])
    if PINNED_NEW_SOURCE_IDS.get(key) != actual:
        raise ValueError("Unreviewed cash-only source cannot upgrade frozen catalog")
    dates = issuer_implementation_dates(text, symbol)
    for k, expected in (
        ("record_date", event["record_date"]),
        ("ex_date", event["ex_date"]),
        ("pay_date", event["scheduled_cash_payment_day"]),
    ):
        if dates.get(k) != expected:
            raise ValueError(f"Original issuer {k} literal mismatch")
    cash = extract_explicit_pretax_cash_per_share(text)
    if len(cash) != 1 or not _decimal_eq(
            cash[0], event["gross_cash_per_old_nominal_share"]):
        raise ValueError("Original issuer gross pre-tax cash mismatch")
    if not (event["announcement_day"] < event["earliest_usable_exchange_day"]
            <= event["record_date"] < event["ex_date"]):
        raise ValueError("Issuer publication embargo or record/ex chronology violated")
    if event["complete_rights_supported_by_issuer_original"]:
        raise ValueError("Previously complete issuer event unexpectedly reclassified")
    for x in ("bonus_shares_per_old_share", "capital_transfer_shares_per_old_share"):
        if event[x] is not None and not _decimal_eq(event[x], 0):
            raise ValueError("Prior source positive share right conflicts with cash-only text")
    return {
        "symbol": symbol,
        "ex_date": event["ex_date"],
        "original_issuer_pdf_sha256": actual,
        "original_issuer_pdf_url": event["issuer_original_pdf_url"],
        "issuer_publication_calendar_day": event["announcement_day"],
        "earliest_usable_exchange_day": event["earliest_usable_exchange_day"],
        "record_date": event["record_date"],
        "scheduled_issuer_payment_day_not_broker_credit": event["scheduled_cash_payment_day"],
        "gross_pretax_cash_per_nominal_share": str(event["gross_cash_per_old_nominal_share"]),
        "zero_bonus_and_transfer_direct_current_issuer_text": True,
        "unchanged_circulating_share_ratio_source_literal": True,
        "new_broker_credited_or_sellable_shares_confirmed": False,
        "broker_cash_credit_or_actual_fills_confirmed": False,
        "source_evidence_grade": SOURCE_GRADE,
    }


def apply_direct_zero_proof(event: dict, proof: dict) -> dict:
    """A fresh derivative row; never mutate existing frozen issuer evidence."""
    if ((event["symbol"], event["ex_date"]) != (proof["symbol"], proof["ex_date"])
        or event["issuer_original_pdf_sha256"] != proof["original_issuer_pdf_sha256"]
        or proof.get("source_evidence_grade") != SOURCE_GRADE
        or proof.get("zero_bonus_and_transfer_direct_current_issuer_text") is not True
        or proof.get("unchanged_circulating_share_ratio_source_literal") is not True
        or event["complete_rights_supported_by_issuer_original"]):
        raise ValueError("Missing original issuer event identity or already complete")
    for x in ("bonus_shares_per_old_share", "capital_transfer_shares_per_old_share"):
        if event[x] is not None and not _decimal_eq(event[x], 0):
            raise ValueError("Cannot erase source-proven positive stock rights")
    out = copy.deepcopy(event)
    out["exp013_prior_rights_evidence"] = copy.deepcopy(out["rights_evidence"])
    out["bonus_shares_per_old_share"] = 0.0
    out["capital_transfer_shares_per_old_share"] = 0.0
    out["full_new_nominal_share_multiplier"] = 1.0
    out["complete_rights_supported_by_issuer_original"] = True
    out["rights_evidence"] = {"bonus": SOURCE_GRADE, "transfer": SOURCE_GRADE}
    out["exp013_additional_direct_current_issuer_pdf_proof"] = copy.deepcopy(proof)
    return out


def run(catalog_path: Path, pdf_dirs: list[Path], out_dir: Path) -> dict:
    if out_dir.exists():
        raise FileExistsError("Will not overwrite an existing source-audit run")
    baseline_bytes = catalog_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    if (baseline.get("kind") != "EXP007_ISSUER_ORIGINAL_BONUS_TRANSFER_AND_CASH_ENTITLEMENT_CATALOG"
        or baseline.get("issuer_events") != 89
        or baseline.get("fully_verified_nominal_share_rights") != 27
        or baseline.get("unknown_share_rights") != 62):
        raise ValueError("Unexpected historical frozen EXP012 catalog / baseline count")
    event_index = {(e["symbol"], e["ex_date"]): e for e in baseline["events"]}
    if len(event_index) != 89 or set(PINNED_NEW_SOURCE_IDS) - set(event_index):
        raise ValueError("Duplicate/missing issuer event identities")
    sha_files: dict[str, Path] = {}
    for d in pdf_dirs:
        if not d.is_dir():
            raise FileNotFoundError(f"Original local issuer PDFs unavailable: {d}")
        for f in d.glob("*.pdf"):
            sha_files[hashlib.sha256(f.read_bytes()).hexdigest()] = f
    proofs = {}
    for key, row in event_index.items():
        f = sha_files.get(row["issuer_original_pdf_sha256"])
        if f is None:
            raise FileNotFoundError(f"Frozen original issuer PDF SHA unavailable: {key}")
        proof = verify_original_issuer_cash_only(row, f.read_bytes())
        if proof is not None:
            proofs[key] = proof
    if set(proofs) != set(PINNED_NEW_SOURCE_IDS):
        raise ValueError("Incomplete or unexpectedly expanded literal-PDF proof set")
    derived = copy.deepcopy(baseline)
    derived["kind"] = "EXP013_SUPPLEMENTAL_DIRECT_CASH_ONLY_ISSUER_RIGHTS_CATALOG"
    derived["derived_from_baseline_catalog_sha256"] = hashlib.sha256(
        baseline_bytes).hexdigest()
    derived["events"] = [
        apply_direct_zero_proof(row, proofs[(row["symbol"], row["ex_date"])])
        if (row["symbol"], row["ex_date"]) in proofs else row
        for row in baseline["events"]
    ]
    derived["fully_verified_nominal_share_rights"] = sum(
        e["complete_rights_supported_by_issuer_original"] for e in derived["events"])
    derived["unknown_share_rights"] = 89 - derived["fully_verified_nominal_share_rights"]
    derived["exp013_added_cash_only_source_proofs"] = len(proofs)
    derived["original_baseline_immutable_and_separately_reproducible"] = True
    if (derived["fully_verified_nominal_share_rights"],
            derived["unknown_share_rights"]) != (32, 57):
        raise ValueError("No fail-open catalog uplift allowed")
    catalog_bytes = (json.dumps(derived, ensure_ascii=False, indent=2) + "\n").encode()
    audit = {
        "kind": "EXP013_FIVE_ORIGINAL_ISSUER_EXPLICIT_CASH_ONLY_COMPLETIONS",
        "baseline_catalog_full_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "derived_catalog_full_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "rehashed_original_issuer_PDF_events": len(event_index),
        "before_complete_and_unresolved": [27, 62],
        "newly_direct_current_issuer_verified_zero_bonus_and_transfer": len(proofs),
        "after_complete_and_unresolved": [32, 57],
        "new_source_fetched_this_run": False,
        "historical_factor_versions_or_broker_credits_verified": False,
        "actual_portfolio_orders_or_returns_recomputed": False,
        "source_proofs": [proofs[k] for k in sorted(proofs)],
    }
    out_dir.mkdir(parents=True)
    (out_dir / "source_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "rights_catalog_exp013.json").write_bytes(catalog_bytes)
    return audit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-catalog", type=Path, required=True)
    p.add_argument("--issuer-pdfs", type=Path, nargs="+", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    audit = run(args.baseline_catalog, args.issuer_pdfs, args.out_dir)
    print(json.dumps({k: v for k, v in audit.items() if k != "source_proofs"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
