"""EXP016: two exact-original, cash-only/no-stock issuer implementation proofs.

Derive a separate 38/51 catalog from immutable EXP014 36/53; neither original
PDFs nor old evidence are modified. Source-verified issuer entitlements are NOT
broker credits, tradeable quantities, official limit prices or real fills.
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

BASE_SHA256 = "f47b34380951ea998f9c494687d2d8f0f2355cea4bfd0ef000bf5eece6ea19d2"
BASE_KIND = "EXP014_SUPPLEMENTAL_ISSUER_CURRENT_ZERO_RIGHTS_CATALOG"
GRADE = "CURRENT_ISSUER_IMPLEMENTATION_EXPLICIT_NO_BONUS_NO_CAPITAL_EXP016"
DIRECT = "本次权益分派不涉及派送红股或转增股本"
TITLE_NAME = "内蒙古伊利实业集团股份有限公司"
PINNED = {
    ("SH600887", "2021-06-11"): {
        "event_id": "fb96a89a9571b9d377995ae5",
        "sha256": "757f3b72dc33925080addf7e3ee826047066c52b10c12ed607190ed70597fbef",
        "fiscal": "2020",
    },
    ("SH600887", "2022-06-01"): {
        "event_id": "d28ccb2336ff54b9253bdbc2",
        "sha256": "9e2789f8a0c3e4716eefaa703e838301bb9200893a64aa2724913b15e939f18b",
        "fiscal": "2021",
    },
}


def source_proves_no_stock(text: str, first_page: str, fiscal: str) -> bool:
    """Reject generic stock-registration boilerplate and prior-year statements."""
    t, head = clean(text), clean(first_page)
    title = f"{TITLE_NAME}{fiscal}年年度权益分派实施公告"
    section = t.find("四、分配实施办法")
    claim = t.find(DIRECT)
    return (title in head and "证券代码：600887" in head and
            section >= 0 and section < claim and claim >= 0 and
            t.count(DIRECT) == 1)


def verify_source(event: dict, content: bytes) -> dict:
    key = (event.get("symbol"), event.get("ex_date"))
    pin = PINNED.get(key)
    if pin is None:
        raise ValueError("Unreviewed issuer event is not an approved proof")
    digest = hashlib.sha256(content).hexdigest()
    if (digest != pin["sha256"] or
            event.get("issuer_original_pdf_sha256") != digest or
            event.get("event_id") != pin["event_id"]):
        raise ValueError("Pinned full SHA256 or issuer event identity mismatch")
    if not content.startswith(b"%PDF"):
        raise ValueError("Original source is not PDF")
    url = event.get("issuer_original_pdf_url")
    notice = event.get("announcement_day")
    if (not isinstance(url, str) or not isinstance(notice, str) or
            re.fullmatch(
                r"https://static\.cninfo\.com\.cn/finalpage/" +
                re.escape(notice) + r"/\d+\.PDF", url,
            ) is None):
        raise ValueError("Original source URL or dated notice invalid")
    reader = PdfReader(BytesIO(content), strict=False)
    if not reader.pages:
        raise ValueError("Missing original issuer PDF pages")
    first = reader.pages[0].extract_text() or ""
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:5])
    if not source_proves_no_stock(text, first, pin["fiscal"]):
        raise ValueError("Explicit CURRENT no-stock-rights issuer proof missing")
    terms = extract_share_terms(text)
    if (terms["bonus_per_ten_distinct_candidates"] or
            terms["transfer_per_ten_distinct_candidates"] or
            terms["bonus_source_status"].startswith("CONFLICTING") or
            terms["transfer_source_status"].startswith("CONFLICTING")):
        raise ValueError("Positive or contradictory source stock rights")
    dates = issuer_implementation_dates(text, event["symbol"])
    if (dates["status"] != "PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED" or
            dates["record_date"] != event["record_date"] or
            dates["ex_date"] != event["ex_date"] or
            dates["pay_date"] != event["scheduled_cash_payment_day"]):
        raise ValueError("Original issuer record/ex/payment dates contradict catalog")
    cash = extract_explicit_pretax_cash_per_share(text)
    if (len(cash) != 1 or
            Decimal(str(cash[0])) != Decimal(str(event["gross_cash_per_old_nominal_share"]))):
        raise ValueError("Original issuer pretax cash terms contradict catalog")
    if not (notice < event["earliest_usable_exchange_day"]
            <= event["record_date"] < event["ex_date"]):
        raise ValueError("Source eligibility or issuer dates invalid")
    if (event["complete_rights_supported_by_issuer_original"] or
            event["bonus_shares_per_old_share"] is not None or
            event["capital_transfer_shares_per_old_share"] is not None or
            event["full_new_nominal_share_multiplier"] is not None):
        raise ValueError("Cannot replace already known or positive share rights")
    for name in ("original_publication_intraday_time_certified",
                 "historical_factor_vintage_available",
                 "broker_share_delivery_and_cash_payment_verified"):
        if event.get(name) is not False:
            raise ValueError("External evidence flag incorrectly promoted")
    return {
        "event_id": event["event_id"], "symbol": key[0], "ex_date": key[1],
        "source_full_sha256": digest, "original_url": url,
        "original_notice_day": notice,
        "original_first_usable_day": event["earliest_usable_exchange_day"],
        "original_record_day": dates["record_date"],
        "original_ex_day": dates["ex_date"],
        "issuer_scheduled_cash_pay_day_not_broker_receipt": dates["pay_date"],
        "original_pretax_cash_per_old_share": str(cash[0]),
        "source_grade": GRADE,
        "explicit_current_no_bonus_and_no_capital": True,
        "intraday_publication_time_proven": False,
        "broker_cash_share_credit_or_sellable_quantity_proven": False,
        "exchange_daily_limit_price_or_order_execution_proven": False,
    }


def apply_proof(row: dict, proof: dict) -> dict:
    key = (row["symbol"], row["ex_date"])
    pin = PINNED.get(key)
    if (pin is None or pin["event_id"] != proof.get("event_id") or
            pin["sha256"] != proof.get("source_full_sha256") or
            proof.get("source_grade") != GRADE or
            proof.get("explicit_current_no_bonus_and_no_capital") is not True or
            row["issuer_original_pdf_sha256"] != proof.get("source_full_sha256") or
            row["complete_rights_supported_by_issuer_original"] or
            row["bonus_shares_per_old_share"] is not None or
            row["capital_transfer_shares_per_old_share"] is not None):
        raise ValueError("Source identity not approved or rights already established")
    original = copy.deepcopy(row)
    result = copy.deepcopy(row)
    result["exp016_previous_rights_evidence"] = copy.deepcopy(row["rights_evidence"])
    result["bonus_shares_per_old_share"] = 0.0
    result["capital_transfer_shares_per_old_share"] = 0.0
    result["full_new_nominal_share_multiplier"] = 1.0
    result["complete_rights_supported_by_issuer_original"] = True
    result["rights_evidence"] = {"bonus": GRADE, "transfer": GRADE}
    result["exp016_original_issuer_proof"] = copy.deepcopy(proof)
    result["exp016_confirmed_missing_zero_categories"] = [
        "bonus_shares_per_old_share", "capital_transfer_shares_per_old_share",
    ]
    frozen = (
        "event_id", "symbol", "announcement_day", "earliest_usable_exchange_day",
        "record_date", "ex_date", "scheduled_cash_payment_day",
        "gross_cash_per_old_nominal_share", "issuer_original_pdf_sha256",
        "issuer_original_pdf_url", "cash_rights_nominal_not_qlib_adjusted",
        "broker_share_delivery_and_cash_payment_verified",
        "historical_factor_vintage_available",
        "original_publication_intraday_time_certified",
    )
    if any(result[k] != original[k] for k in frozen):
        raise AssertionError("Issuer claim upgrade mutated old cash/source/time evidence")
    return result


def run(baseline_catalog: Path, pdf_dirs: list[Path], out_dir: Path) -> dict:
    if out_dir.exists():
        raise FileExistsError("Refusing overwrite of any prior evidence run")
    source = baseline_catalog.read_bytes()
    if hashlib.sha256(source).hexdigest() != BASE_SHA256:
        raise ValueError("Immutable baseline catalog full SHA256 mismatch")
    old = json.loads(source)
    if (old.get("kind") != BASE_KIND or
            (old.get("issuer_events"), old.get("fully_verified_nominal_share_rights"),
             old.get("unknown_share_rights")) != (89, 36, 53)):
        raise ValueError("Wrong frozen 36/53 base catalog")
    rows = old["events"]
    bykey = {(r["symbol"], r["ex_date"]): r for r in rows}
    if len(rows) != 89 or len(bykey) != 89 or not set(PINNED) <= set(bykey):
        raise ValueError("Wrong or duplicate issuer event identities")
    byhash: dict[str, Path] = {}
    for folder in pdf_dirs:
        if not folder.is_dir():
            raise FileNotFoundError(f"Original issuer PDF archive not accessible: {folder}")
        for path in folder.glob("*.pdf"):
            byhash[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    for row in rows:
        digest = row["issuer_original_pdf_sha256"]
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("Missing original source SHA256")
        if digest not in byhash:
            raise FileNotFoundError("Unverified original PDF event: " + row["event_id"])
        if hashlib.sha256(byhash[digest].read_bytes()).hexdigest() != digest:
            raise ValueError("Archived issuer PDF changed while auditing")
    proofs = {}
    for key, pin in PINNED.items():
        proofs[key] = verify_source(bykey[key], byhash[pin["sha256"]].read_bytes())
    derived = copy.deepcopy(old)
    derived["kind"] = "EXP016_SUPPLEMENTAL_EXPLICIT_NO_STOCK_ISSUER_RIGHTS_CATALOG"
    derived["source_exp014_catalog_full_sha256"] = BASE_SHA256
    derived["events"] = [
        apply_proof(row, proofs[(row["symbol"], row["ex_date"])])
        if (row["symbol"], row["ex_date"]) in proofs else copy.deepcopy(row)
        for row in rows
    ]
    derived["fully_verified_nominal_share_rights"] = sum(
        r["complete_rights_supported_by_issuer_original"] for r in derived["events"])
    derived["unknown_share_rights"] = 89 - derived["fully_verified_nominal_share_rights"]
    derived["exp016_added_exact_original_source_proofs"] = 2
    derived["exp016_newly_proven_zero_stock_categories"] = 4
    if (derived["fully_verified_nominal_share_rights"],
            derived["unknown_share_rights"]) != (38, 51):
        raise AssertionError("Derived source-completeness cardinality invalid")
    output_bytes = (json.dumps(derived, indent=2, ensure_ascii=False) + "\n").encode()
    audit = {
        "kind": "EXP016_TWO_DIRECT_ISSUER_CASH_ONLY_NO_STOCK_RIGHTS_PROOFS",
        "frozen_exp014_full_sha256": BASE_SHA256,
        "derived_exp016_full_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "original_event_pdf_sha256s_rechecked": len(rows),
        "direct_current_issuer_proofs": len(proofs),
        "new_zero_share_categories": 4,
        "before_complete_unresolved": [36, 53],
        "after_complete_unresolved": [38, 51],
        "original_pdf_new_downloads": 0,
        "original_or_prior_catalog_mutation": False,
        "independent_historical_factor_vintage_proven": False,
        "broker_credit_or_saleable_shares_proven": False,
        "official_daily_price_limit_or_auction_fills_proven": False,
        "historical_portfolio_returns_validated": False,
        "original_evidence": [proofs[k] for k in sorted(proofs)],
    }
    out_dir.mkdir(parents=True)
    (out_dir / "rights_catalog_exp016.json").write_bytes(output_bytes)
    (out_dir / "source_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-catalog", type=Path, required=True)
    p.add_argument("--issuer-pdfs", type=Path, nargs="+", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()
    audit = run(a.baseline_catalog, a.issuer_pdfs, a.out_dir)
    print(json.dumps(audit, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
