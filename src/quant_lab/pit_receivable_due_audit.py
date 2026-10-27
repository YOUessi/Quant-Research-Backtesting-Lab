"""EXP-011: original-PDF, raw-price backed issuer *due-date* receivable audit.

The issuer's stated payment date NEVER establishes that a particular broker
credited the cash. Keep the gross pre-tax claim, mark it CREDIT_UNVERIFIED,
and never turn it into spendable portfolio cash absent independent receipts.
This is a no-trade price/accounting scenario, not a financial result.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader

from .pit_capital_balance import audit_balanced_issuer_rights
from .pit_nominal_book import simulate_nominal_right
from .pit_official_batch import extract_explicit_pretax_cash_per_share
from .pit_original_date_recovery import issuer_implementation_dates
from .pit_share_distribution import clean, extract_share_terms

# Independently fixed from previously archived original inputs. Neither the
# current catalog nor arbitrary downloaded replacements can rewrite these IDs.
PINS = {
    ("SH600276", "2021-06-10"): {
        "pdf": "SH600276_2021-06-04_1210161820.pdf",
        "pdf_sha256": "b731dec60e78bc92eab572ed099ec9da59fed84d6f06bb35fab605f4cb00a2f4",
        "csv_sha256": "a80ae4f88ba9270894a9b88fc85bc408ecac27eefa9eeb6b9ea78d1a56e387af",
        "meta_sha256": "cb69c39d64ade78f47702604aa845d7a1cec2af40aed63428ae7013395dac373",
        "http_response_sha256": "d43cfd262720de58bfab609a6677d5be9f17d9a19892b80aebf71b834e91e212",
        "usable": "2021-06-07", "pay": "2021-06-11",
        "record": "2021-06-09", "cash": "0.2", "bonus": "0.2", "transfer": "0",
    },
    ("SH600760", "2021-06-24"): {
        "pdf": "SH600760_2021-06-16_1210238262.pdf",
        "pdf_sha256": "6ee4d90b8e4d0fc49420a70df6a3a1ea148ad5e2d0a99f208fbb2d8358ddfec8",
        "csv_sha256": "3309549d85141db76af7673db4ab4dccd663dd40091861f3a17199b490eb9843",
        "meta_sha256": "02ee3ebc77b1e5cd68905262ff747126922222e82aa9443e5f0b8f5be7c136d6",
        "http_response_sha256": "0de246a255a6e368f1c38df3828b30c0507a3fcfe02255097f3d671a8ae5f4df",
        "usable": "2021-06-17", "pay": "2021-06-25",
        "record": "2021-06-23", "cash": "0.24", "bonus": "0", "transfer": "0.4",
    },
    ("SH603392", "2022-04-21"): {
        "pdf": "SH603392_2022-04-15_1212921735.pdf",
        "pdf_sha256": "0ee03e64cad8b1b2ed6a2164f212f3d0ece474a99efa52f0dbcde2b021ecc7d1",
        "csv_sha256": "c72a6230fc54f5a6935eb14466e0c4734befd0393b3397f331563169ca63560c",
        "meta_sha256": "547d58241077615dee3edef398f5358c82d032300e12ad63f7366debb389c0a6",
        "http_response_sha256": "8779e44268cd81cecc2245dc9448355e98dee77d037cc6a2cf0f1e4efbd361f8",
        "usable": "2022-04-18", "pay": "2022-04-22",
        "record": "2022-04-20", "cash": "0.2", "bonus": "0.2", "transfer": "0.25",
    },
}


def verified_sha(data: bytes, expected: str, label: str) -> str:
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError(f"Invalid pinned SHA256 for {label}")
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f"Original bytes SHA256 mismatch: {label}")
    return actual


def same_number(actual, expected, label: str) -> None:
    if actual is None or abs(Decimal(str(actual)) - Decimal(str(expected))) > Decimal("0.000000001"):
        raise ValueError(f"Original issuer {label} disagrees with frozen rights")


def verify_issuer_original(row: dict, pdf: bytes, pin: dict) -> dict:
    if not row.get("complete_rights_supported_by_issuer_original"):
        raise ValueError("Partial corporate share-rights must remain held")
    if (row.get("earliest_usable_exchange_day") != pin["usable"]
        or row.get("scheduled_cash_payment_day") != pin["pay"]
        or row.get("record_date") != pin["record"]
        or row.get("earliest_usable_exchange_day") > row.get("record_date")):
        raise ValueError("Issuer corporate-action date/publication embargo mismatch")
    verified_sha(pdf, pin["pdf_sha256"], "issuer PDF")
    if row.get("issuer_original_pdf_sha256") != pin["pdf_sha256"]:
        raise ValueError("Catalog issuer PDF SHA mismatch")
    if not row.get("issuer_original_pdf_url", "").startswith("https://static.cninfo.com.cn/finalpage/"):
        raise ValueError("Missing original issuer source URL")
    for key, name in (("cash", "gross_cash_per_old_nominal_share"),
                      ("bonus", "bonus_shares_per_old_share"),
                      ("transfer", "capital_transfer_shares_per_old_share")):
        same_number(row.get(name), pin[key], key)
    text = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(pdf)).pages[:5])
    if row["symbol"][2:] not in clean(text):
        raise ValueError("Issuer original stock code absent")
    dates = issuer_implementation_dates(text, row["symbol"])
    for k, expected in (("record_date", pin["record"]), ("ex_date", row["ex_date"]), ("pay_date", pin["pay"])):
        if dates.get(k) != expected:
            raise ValueError("Issuer original publication literal-date mismatch")
    money = extract_explicit_pretax_cash_per_share(text)
    if len(money) != 1:
        raise ValueError("Original PDF cash is ambiguous or not explicit gross")
    same_number(money[0], pin["cash"], "gross cash")
    parsed = extract_share_terms(text)
    for cat in ("bonus", "transfer"):
        found = parsed[f"{cat}_ratio_per_nominal_share"]
        source_grade = row["rights_evidence"][cat]
        expected = row[f"{'bonus' if cat == 'bonus' else 'capital_transfer'}_shares_per_old_share"]
        if source_grade.startswith("EXPLICIT_ISSUER_"):
            same_number(found, expected, cat)
        elif source_grade == "DERIVED_ZERO_BY_ISSUER_PRE_POST_AND_ISSUED_SHARE_BALANCE":
            if found is not None or Decimal(str(expected)) != 0:
                raise ValueError("Complementary issuer right was not a derived zero")
            flag = re.findall(r"差异化分红送转[：:]([是否])", clean(text))
            differential = {"是": True, "否": False}.get(flag[-1]) if len(set(flag)) == 1 else None
            proof = audit_balanced_issuer_rights(
                text, parsed, issuer_sha256=pin["pdf_sha256"],
                is_differential_distribution=differential)
            if proof.get("balanced_accounting_inferred_zero_category") != cat:
                raise ValueError("Source capital conservation does not prove derived zero")
            saved = row.get("capital_issuer_balance_extra_proof") or {}
            for label, key in (("company_before", "pre_nominal_company_shares"),
                               ("company_after", "post_nominal_company_shares"),
                               ("new_issued_shares", "issuer_explicit_new_share_quantity")):
                if saved.get(label) != proof.get(key):
                    raise ValueError("Issuer capital arithmetic inconsistent with catalog")
        else:
            raise ValueError("Unrecognized rights source evidence grade")
    return {"original_pdf_sha256": pin["pdf_sha256"],
            "source_dates_reparsed": True,
            "gross_cash_and_all_share_rights_reparsed": True}


def audit_one(row: dict, pin: dict, *, pdf_bytes: bytes,
              csv_bytes: bytes, metadata_bytes: bytes) -> dict:
    source = verify_issuer_original(row, pdf_bytes, pin)
    verified_sha(csv_bytes, pin["csv_sha256"], "unadjusted daily CSV")
    verified_sha(metadata_bytes, pin["meta_sha256"], "quote source metadata")
    meta = json.loads(metadata_bytes)
    if (meta.get("source") != "EASTMONEY_PUBLIC_DAILY_UNADJUSTED_BAR"
        or meta.get("response_body_sha256") != pin["http_response_sha256"]
        or meta.get("not_actual_order_fill") is not True):
        raise ValueError("Unadjusted quote source metadata is not intact")
    bars = pd.read_csv(BytesIO(csv_bytes))
    if (bars["symbol"].nunique() != 1 or bars["symbol"].iloc[0] != row["symbol"]
        or bars["date"].duplicated().any()
        or not bars["close_raw"].gt(0).all()
        or not bars["volume_lots"].gt(0).all()):
        raise ValueError("Original ticker/dated trade-price validity failed")
    event = {
        "event_id": row["event_id"], "symbol": row["symbol"],
        "record_date": row["record_date"], "ex_date": row["ex_date"],
        "payment_date": row["scheduled_cash_payment_day"],
        "gross_cash_per_nominal_share": row["gross_cash_per_old_nominal_share"],
        "issuer_pdf_sha256": pin["pdf_sha256"],
        "earliest_usable_exchange_day": pin["usable"],
        "evidence_grade": "ORIGINAL_ISSUER_CASH_BONUS_TRANSFER_SOURCE_PROVEN",
    }
    ratio = Decimal(pin["bonus"]) + Decimal(pin["transfer"])
    book = simulate_nominal_right(
        event, bars[["date", "close_raw"]], original_shares=1000,
        share_bonus_ratio=str(ratio), share_bonus_terms_officially_verified=True)
    due = [x for x in book["records"] if x["date"] >= pin["pay"]]
    later = [x for x in book["records"] if x["date"] >= row["ex_date"]]
    amount = Decimal("1000") * Decimal(pin["cash"])
    if not due or not later:
        raise ValueError("Missing observed quote sessions on/after scheduled issuer pay day")
    if (any(Decimal(x["pretax_receivable"]) != amount for x in later)
        or any(Decimal(x["cash_schedule_only"]) != 0 for x in book["records"])
        or any(x["gross_receivable_credit_status"] != "ISSUER_SCHEDULE_REACHED_CREDIT_UNVERIFIED" for x in due)
        or not book["source_schedule_reached_within_quote_window"]):
        raise ValueError("Issuer schedule accidentally promoted to received broker cash")
    return {
        "symbol": row["symbol"], "ex_date": row["ex_date"],
        "scheduled_issuer_payment_date": pin["pay"],
        "original_issuer_provenance": source,
        "unadjusted_daily_csv_sha256": pin["csv_sha256"],
        "vendor_response_metadata_file_sha256": pin["meta_sha256"],
        "vendor_reported_http_response_sha256_not_raw_reverified": pin["http_response_sha256"],
        "frozen_source_quote_last_day": book["records"][-1]["date"],
        "hypothetical_initial_shares": "1000",
        "ex_day_entitled_nominal_shares": next(x["nominal_shares"] for x in later),
        "gross_pretax_cash_claim_cny": str(amount),
        "gross_pretax_claim_remaining_at_final_available_quote_day_cny":
            book["records"][-1]["pretax_receivable"],
        "issuer_schedule_reached_quotation_days": len(due),
        "broker_cash_credit_obtained": False,
        "broker_issued_share_credit_obtained": False,
        "cash_credited_to_spendable_balance_cny": "0",
        "gross_claim_is_verified_broker_asset_value": False,
        "quoted_stock_rights_are_not_certified_sellable_new_shares": True,
        "no_trades_no_model_return_adjustment": True,
    }


def run(*, catalog_path: Path, pdf_dirs: list[Path],
        raw_quotes_dir: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Do not overwrite earlier research results")
    catalog = json.loads(catalog_path.read_text("utf-8"))
    if (catalog.get("kind") != "EXP007_ISSUER_ORIGINAL_BONUS_TRANSFER_AND_CASH_ENTITLEMENT_CATALOG"
        or catalog.get("issuer_events") != 89
        or catalog.get("fully_verified_nominal_share_rights") != 27
        or catalog.get("unknown_share_rights") != 62):
        raise ValueError("Issuer-action source catalog scope changed")
    index = {(x["symbol"], x["ex_date"]): x for x in catalog["events"]}
    if len(index) != 89:
        raise ValueError("Duplicate frozen issuer actions")
    cases = []
    for key, pin in PINS.items():
        pdf_files = [d / pin["pdf"] for d in pdf_dirs if (d / pin["pdf"]).is_file()]
        if len(pdf_files) != 1:
            raise FileNotFoundError("Exactly one pinned original PDF required: " + pin["pdf"])
        csv_file = raw_quotes_dir / f"{key[0]}_{key[1]}_raw.csv"
        meta_file = raw_quotes_dir / f"{key[0]}_{key[1]}_source.json"
        cases.append(audit_one(index[key], pin, pdf_bytes=pdf_files[0].read_bytes(),
                               csv_bytes=csv_file.read_bytes(),
                               metadata_bytes=meta_file.read_bytes()))
    result = {
        "kind": "EXP011_ORIGINAL_ISSUER_CASH_DUE_UNSETTLED_RECEIVABLE_AUDIT",
        "source_issuer_events_unchanged": 89,
        "issuer_complete_rights_unchanged": 27,
        "issuer_incomplete_rights_unchanged": 62,
        "verified_original_issuer_PDF_and_quote_csv_cases": len(cases),
        "scheduled_payment_dates_are_not_actual_broker_cash_credit": True,
        "historical_adjustment_vintage_verified": False,
        "actual_account_cash_tax_or_share_delivery_verified": False,
        "real_execution_or_model_return_verified": False,
        "cases": cases,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rights-catalog", type=Path, required=True)
    p.add_argument("--original-pdfs", type=Path, nargs="+", required=True)
    p.add_argument("--raw-quote-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    r = run(catalog_path=a.rights_catalog, pdf_dirs=a.original_pdfs,
            raw_quotes_dir=a.raw_quote_dir, out=a.out)
    print(json.dumps({"verified_original_cases": len(r["cases"]),
                      "gross_receivable_not_spendable_cash": True,
                      "broker_credit_proven": False}, indent=2))


if __name__ == "__main__":
    main()
