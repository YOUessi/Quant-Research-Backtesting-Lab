"""EXP014: four SHA-pinned original-issuer stock-rights completions.

Derive a NEW 36/53 rights catalog from the immutable EXP013 32/57 catalog.
This is an issuer-rights evidence audit, not security delivery, broker cash,
trade execution, PIT factor-vintage reconstruction, or actual market PnL.

Only separately pinned original implementation PDFs can prove stock-rights
zeros. Preserve all previous fields, especially previously unknown payment day.
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
from .pit_original_date_recovery import (
    issuer_implementation_dates, normalize_date, SZ_CASH_PAY,
)
from .pit_share_distribution import clean, extract_share_terms

EXP013_CATALOG_SHA256 = "54c3a094fa49614145db2434180a6cf4326ba1c8abf807a9e667fa8b19b8cfcf"
GRADE_SSE = "DIRECT_CURRENT_CASH_ONLY_WITH_ZERO_CIRCULATING_CHANGE_EXP014"
GRADE_SZ = "DIRECT_IMPLEMENTED_ANNUAL_NO_CAPITAL_NO_BONUS_EXP014"
# Exact approved identities, fixed before the actual four-source replay.
# These are *the archived PDF file bytes*, not vendor-provided short hashes.
PINNED = {
    ("SH600276", "2022-07-05"): {
        "event_id": "4385fb453727b4092cd7593a",
        "sha256": "48b04cf9ac8bc55f84b1cfd6b91056ccc8e10760260a6501ea5de045819ef91d",
        "fiscal": "2021",
        "grade": GRADE_SSE,
    },
    ("SH601225", "2021-07-09"): {
        "event_id": "80b45b246e5ed00c00ac56af",
        "sha256": "f40033ab555ffa4f8f02d9030f1a1bafe1305ab818f8e0e75f0148eb23f1b8b6",
        "fiscal": "2020",
        "grade": GRADE_SSE,
    },
    ("SZ300676", "2021-07-07"): {
        "event_id": "b2b008c5681f68140fdb796a",
        "sha256": "fe930ea2ab5fa604e77400435677832031a79129d5779cb752f1556ebb021c5c",
        "fiscal": "2020",
        "grade": GRADE_SZ,
    },
    ("SZ300676", "2022-07-06"): {
        "event_id": "1c4d49e7d327d8e4db7e3082",
        "sha256": "f318dbe9d4e53b1c6777a3760f41356bfee9ce1472bfc4b3baf02fd069df380f",
        "fiscal": "2021",
        "grade": GRADE_SZ,
    },
}

SSE_CASH_ONLY_1 = re.compile(
    r"公司本次仅进行现金红利分配[，,]?无送转方案[，,]?因此[，,]?"
    r"公司流通股不会发生变化[，,]?流通股份变动比例为0"
)
SSE_CASH_ONLY_2 = re.compile(
    r"公司本次利润分配仅进行现金红利分配.{0,90}?无送股和转增分配[。，,]?"
    r"公司流通股不会发生变化[，,]?流[通动]股份变动比例为0"
)
SZ_DATE_LITERAL = re.compile(
    r"本次权益分派股权登记日为[:：](20\d{2}年\d{1,2}月\d{1,2}日)"
    r"[，,]?"
    r"除权除息日为[:：](20\d{2}年\d{1,2}月\d{1,2}日)"
)


def source_proves_both_zero(text: str, header: str, fiscal: str,
                            grade: str) -> bool:
    """Require CURRENT distribution plan, not a hypothetical formula or old plan.

    An issuer's announcement/title and precise dates are checked separately.
    """
    t = clean(text)
    head = clean(header)
    if f"{fiscal}年年度权益分派实施公告" not in head:
        return False
    if grade == GRADE_SSE:
        return bool(SSE_CASH_ONLY_1.search(t) or SSE_CASH_ONLY_2.search(t))
    if grade == GRADE_SZ:
        explicit_no_stock = (
            f"{fiscal}年度公司不实施以资本公积转增股本，不送红股" in t
        )
        unchanged_since_approval = (
            "自本次权益分派方案披露至实施期间，公司股本总额及公司回购专用"
            "证券账户持有的股份数均未发生变化" in t
        )
        implemented_same_year = (
            f"本次实施的分配方案与公司{fiscal}年年度股东大会审议通过的"
            "分配方案一致" in t
        )
        return explicit_no_stock and unchanged_since_approval and implemented_same_year
    raise ValueError("Unsupported issuer rights proof grade")


def literal_issuer_dates(text: str, event: dict) -> dict:
    """Exact source dates, with one narrowly recognized SZ no-comma layout.

    Never synthesize dates from file names or a vendor's ex-date columns.
    The legacy parser does not recognize the 2022 SZ wording lacking a comma.
    """
    original = issuer_implementation_dates(text, event["symbol"])
    if original["status"] == "PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED":
        return original
    key = (event["symbol"], event["ex_date"])
    if key != ("SZ300676", "2022-07-06"):
        raise ValueError("Original issuer dates unavailable or ambiguous")
    t = clean(text)
    values = sorted(set(
        (normalize_date(a), normalize_date(b))
        for a, b in SZ_DATE_LITERAL.findall(t)
    ))
    payments = sorted(set(
        normalize_date(s) for s in SZ_CASH_PAY.findall(t)
    ))
    if len(values) != 1 or len(payments) != 1:
        raise ValueError("Pinned original SZ effective-day/payment literals ambiguous")
    record, ex_day = values[0]
    pay = payments[0]
    if not record < ex_day <= pay:
        raise ValueError("Issuer record/ex/scheduled-pay chronology invalid")
    return {
        "record_date": record, "ex_date": ex_day, "pay_date": pay,
        "status": "PINNED_SZ_2022_ORIGINAL_LITERAL_NO_COMMA_RECOVERED",
    }


def verify_source(event: dict, pdf_bytes: bytes) -> dict:
    key = (event["symbol"], event["ex_date"])
    pin = PINNED.get(key)
    if pin is None:
        raise ValueError("Cannot approve an unreviewed issuer original")
    digest = event.get("issuer_original_pdf_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Original full SHA256 required")
    actual = hashlib.sha256(pdf_bytes).hexdigest()
    if (actual != digest or actual != pin["sha256"]
            or event.get("event_id") != pin["event_id"]):
        raise ValueError("Pinned original issuer SHA256 / event identity mismatch")
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Original announcement is not PDF bytes")
    url = event.get("issuer_original_pdf_url", "")
    notice = event.get("announcement_day", "")
    if not isinstance(url, str) or not url.startswith(
            f"https://static.cninfo.com.cn/finalpage/{notice}/"):
        raise ValueError("Original issuer PDF host or announcement-day path mismatch")
    reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    if not reader.pages:
        raise ValueError("Original issuer PDF has no readable pages")
    first_page = reader.pages[0].extract_text() or ""
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:5])
    head = clean(first_page)
    if (event["symbol"][2:] not in head or
            "权益分派实施公告" not in head):
        raise ValueError("Original A-stock identifier or implementation title absent")
    if not source_proves_both_zero(text, first_page, pin["fiscal"], pin["grade"]):
        raise ValueError("Explicit CURRENT issuer zero-rights proof missing")
    rights = extract_share_terms(text)
    if (rights["bonus_per_ten_distinct_candidates"] or
        rights["transfer_per_ten_distinct_candidates"] or
        rights["bonus_source_status"].startswith("CONFLICTING") or
        rights["transfer_source_status"].startswith("CONFLICTING")):
        raise ValueError("Original PDF has conflicting positive issuer share rights")
    dates = literal_issuer_dates(text, event)
    for name, expected in (
        ("record_date", event["record_date"]),
        ("ex_date", event["ex_date"]),
    ):
        if dates[name] != expected:
            raise ValueError("Issuer original record/ex effective day disagrees with event")
    old_payment = event.get("scheduled_cash_payment_day")
    if old_payment is not None and dates["pay_date"] != old_payment:
        raise ValueError("Issuer scheduled-pay day contradicts existing source")
    cash = extract_explicit_pretax_cash_per_share(text)
    if (len(cash) != 1 or
            Decimal(str(cash[0])) != Decimal(str(event["gross_cash_per_old_nominal_share"]))):
        raise ValueError("Original issuer gross pre-tax cash does not match catalog")
    if not (notice < event["earliest_usable_exchange_day"]
            <= event["record_date"] < event["ex_date"]):
        raise ValueError("Frozen publication embargo/stock-day chronology invalid")
    if event["complete_rights_supported_by_issuer_original"]:
        raise ValueError("Cannot supersede already-complete event")
    for col in ("bonus_shares_per_old_share",
                "capital_transfer_shares_per_old_share"):
        old = event[col]
        if old is not None and Decimal(str(old)) != Decimal(0):
            raise ValueError("Cannot overwrite prior positive stock entitlement")
    return {
        "event_id": event["event_id"],
        "symbol": event["symbol"],
        "ex_date": event["ex_date"],
        "issuer_pdf_url": url,
        "issuer_pdf_sha256_full": actual,
        "issuer_original_publication_day": notice,
        "earliest_usable_exchange_day_from_prior_catalog": event["earliest_usable_exchange_day"],
        "record_date_direct_original": dates["record_date"],
        "ex_date_direct_original": dates["ex_date"],
        "issuer_scheduled_payment_day_literal_not_broker_credit": dates["pay_date"],
        "prior_catalog_issuer_scheduled_payment_day_unchanged": old_payment,
        "original_date_extraction_grade": dates["status"],
        "gross_pretax_cash_per_old_share": str(event["gross_cash_per_old_nominal_share"]),
        "both_zero_issuer_text": True,
        "source_grade": pin["grade"],
        "broker_actual_cash_credit_proven": False,
        "broker_share_credit_or_sellable_stock_proven": False,
        "actual_market_order_or_fill_proven": False,
    }


def append_source_proof(event: dict, proof: dict) -> dict:
    key = (event["symbol"], event["ex_date"])
    if (key not in PINNED or event.get("event_id") != proof.get("event_id")
        or key != (proof.get("symbol"), proof.get("ex_date"))
        or PINNED[key]["sha256"] != proof.get("issuer_pdf_sha256_full")
        or event["issuer_original_pdf_sha256"] != proof.get("issuer_pdf_sha256_full")
        or proof.get("source_grade") != PINNED[key]["grade"]
        or proof.get("both_zero_issuer_text") is not True
        or event["complete_rights_supported_by_issuer_original"]):
        raise ValueError("Original issuer proof identity missing or already complete")
    old = copy.deepcopy(event)
    newly_evidenced = []
    for name in ("bonus_shares_per_old_share",
                 "capital_transfer_shares_per_old_share"):
        v = event[name]
        if v is not None and Decimal(str(v)) != 0:
            raise ValueError("Cannot overwrite source-positive stock rights")
        if v is None:
            newly_evidenced.append(name)
    out = copy.deepcopy(event)
    out["exp014_prior_rights_evidence"] = copy.deepcopy(event["rights_evidence"])
    out["bonus_shares_per_old_share"] = 0.0
    out["capital_transfer_shares_per_old_share"] = 0.0
    out["full_new_nominal_share_multiplier"] = 1.0
    out["complete_rights_supported_by_issuer_original"] = True
    for field, evidence_key in (
        ("bonus_shares_per_old_share", "bonus"),
        ("capital_transfer_shares_per_old_share", "transfer"),
    ):
        if field in newly_evidenced:
            out["rights_evidence"][evidence_key] = proof["source_grade"]
    out["exp014_newly_proven_stock_zero_categories"] = newly_evidenced
    out["exp014_original_issuer_proof"] = copy.deepcopy(proof)
    for k in (
        "announcement_day", "earliest_usable_exchange_day",
        "record_date", "ex_date", "scheduled_cash_payment_day",
        "gross_cash_per_old_nominal_share",
        "broker_share_delivery_and_cash_payment_verified",
    ):
        if out[k] != old[k]:
            raise AssertionError("Issuer source audit modified frozen cash/time/broker fields")
    return out


def run(baseline_catalog: Path, pdf_dirs: list[Path], destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError("Never replace a prior original-evidence audit output")
    baseline_bytes = baseline_catalog.read_bytes()
    if hashlib.sha256(baseline_bytes).hexdigest() != EXP013_CATALOG_SHA256:
        raise ValueError("Frozen EXP013 derivative catalog full SHA256 mismatch")
    old = json.loads(baseline_bytes)
    if (old["kind"] != "EXP013_SUPPLEMENTAL_DIRECT_CASH_ONLY_ISSUER_RIGHTS_CATALOG"
        or (old["issuer_events"], old["fully_verified_nominal_share_rights"],
            old["unknown_share_rights"]) != (89, 32, 57)):
        raise ValueError("Wrong frozen issuer source catalog")
    index = {(r["symbol"], r["ex_date"]): r for r in old["events"]}
    if len(index) != 89 or not set(PINNED) <= set(index):
        raise ValueError("Duplicate or missing original cash-rights event")
    byhash = {}
    for directory in pdf_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(f"Archived original issuer directory unavailable: {directory}")
        for path in directory.glob("*.pdf"):
            byhash[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    # Rehash and require EVERY source; only four targeted original PDFs are
    # upgraded. Unchanged source/rights evidence is immutable.
    for row in old["events"]:
        digest = row["issuer_original_pdf_sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or digest not in byhash:
            raise ValueError(f"Missing SHA-pinned original issuer PDF: {row['event_id']}")
        if hashlib.sha256(byhash[digest].read_bytes()).hexdigest() != digest:
            raise ValueError("Original issuer PDF mutated during scan")
    proofs = {}
    for key, pin in PINNED.items():
        row = index[key]
        if row["issuer_original_pdf_sha256"] != pin["sha256"]:
            raise ValueError("Approved original issuer source SHA mismatch")
        proofs[key] = verify_source(row, byhash[pin["sha256"]].read_bytes())
    derived = copy.deepcopy(old)
    derived["kind"] = "EXP014_SUPPLEMENTAL_ISSUER_CURRENT_ZERO_RIGHTS_CATALOG"
    derived["source_exp013_catalog_full_sha256"] = EXP013_CATALOG_SHA256
    derived["events"] = [
        append_source_proof(row, proofs[(row["symbol"], row["ex_date"])])
        if (row["symbol"], row["ex_date"]) in proofs else copy.deepcopy(row)
        for row in old["events"]
    ]
    derived["fully_verified_nominal_share_rights"] = sum(
        bool(row["complete_rights_supported_by_issuer_original"]) for row in derived["events"]
    )
    derived["unknown_share_rights"] = 89 - derived["fully_verified_nominal_share_rights"]
    derived["exp014_added_exact_original_source_proofs"] = len(proofs)
    derived["exp014_bonus_or_transfer_zero_categories_newly_confirmed"] = sum(
        len(row.get("exp014_newly_proven_stock_zero_categories", []))
        for row in derived["events"]
    )
    if ((derived["fully_verified_nominal_share_rights"], derived["unknown_share_rights"])
            != (36, 53) or
            derived["exp014_bonus_or_transfer_zero_categories_newly_confirmed"] != 6):
        raise AssertionError("Unexpected derived issuer stock-rights cardinality")
    content = (json.dumps(derived, ensure_ascii=False, indent=2) + "\n").encode()
    proof_list = [proofs[k] for k in sorted(proofs)]
    audit = {
        "kind": "EXP014_FOUR_ADDITIONAL_SHA_VERIFIED_ISSUER_ZERO_RIGHTS_COMPLETIONS",
        "frozen_exp013_catalog_full_sha256": EXP013_CATALOG_SHA256,
        "new_exp014_catalog_full_sha256": hashlib.sha256(content).hexdigest(),
        "original_issuer_pdf_event_hashes_rechecked": 89,
        "source_proofs_verified": 4,
        "newly_established_zero_stock_right_categories": 6,
        "old_completed_unknown": [32, 57],
        "derived_completed_unknown": [36, 53],
        "source_pdfs_newly_downloaded": False,
        "raw_source_documents_or_old_audits_mutated": False,
        "actual_broker_cash_or_share_postings_verified": False,
        "actual_trading_price_limits_auction_fills_or_returns_verified": False,
        "source_proofs": proof_list,
    }
    destination.mkdir(parents=True)
    (destination / "rights_catalog_exp014.json").write_bytes(content)
    (destination / "source_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-catalog", type=Path, required=True)
    p.add_argument("--issuer-pdfs", type=Path, nargs="+", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    result = run(args.baseline_catalog, args.issuer_pdfs, args.out_dir)
    print(json.dumps({k: v for k, v in result.items()
                      if k != "source_proofs"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
