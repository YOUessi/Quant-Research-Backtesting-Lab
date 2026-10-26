"""EXP-007 issuer-original new-share listing schedule and conservative trade gate.

A source-issued bonus/capital transfer share entitlement is valued from the
ex-date, but stock issued to a particular holder is NOT an observed brokerage
settlement and may become publicly trade-eligible on a later date. The
original issuer PDF often explicitly distinguishes:
  record day | ex day | new unrestricted share-listing day | cash pay day

This gate reports *at most* schedule-based trade availability, not proof
of broker credit, share restrictions, auction limit, or an executable fill.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader


SSE_TABLE = re.compile(
    r"新增无限售条件流通股份上市日现金红利发放日"
    r"(?:A股|Ａ股)"
    r"(\d{4}/\d{1,2}/\d{1,2})[－-]"
    r"(\d{4}/\d{1,2}/\d{1,2})"
    r"(\d{4}/\d{1,2}/\d{1,2})"
    r"(\d{4}/\d{1,2}/\d{1,2})"
)


def issuer_sse_new_share_listing_date(text: str, *, record: str, ex: str) -> dict:
    clean=re.sub(r"\s+","",text).replace("Ａ","A")
    dates={
        (
            str(pd.Timestamp(a.replace("/","-")).date()),
            str(pd.Timestamp(b.replace("/","-")).date()),
            str(pd.Timestamp(c.replace("/","-")).date()),
            str(pd.Timestamp(d.replace("/","-")).date()),
        )
        for a,b,c,d in SSE_TABLE.findall(clean)
    }
    if len(dates)!=1:
        return {
            "status":"UNKNOWN_OR_AMBIGUOUS_ISSUER_NEW_SHARE_LISTING_DATE",
            "new_unrestricted_shares_listing_day":None,
            "issuer_tabular_row_count":len(dates),
        }
    r,x,listing,pay=next(iter(dates))
    if (r!=record or x!=ex or listing<x or pay<x):
        raise ValueError("Issuer table listing/record/ex/cash day contradictory")
    return {
        "status":"ISSUER_ORIGINAL_UNRESTRICTED_NEW_SHARE_LISTING_CALENDAR_DAY",
        "new_unrestricted_shares_listing_day":listing,
        "issuer_scheduled_cash_payment_day":pay,
        "issuer_record_date":r,"issuer_ex_date":x,
        "intraday_broker_share_allocation_certified":False,
        "individual_shares_unrestricted_verified":False,
        "auction_buy_sell_limit_certified":False,
    }


def nominal_trade_availability(event: dict, listing: dict, *, day: str,
                               original_nominal_shares: int,
                               original_shares_independently_confirmed_sellable: bool=False,
                               broker_new_share_credit_verified: bool=False) -> dict:
    """Sell order gate only, no execution simulation.

    Never allows bonus/transfer shares as tradeable before listed date.
    If original holding itself is not independently tradeable/credited, returns
    UNKNOWN; no fictitious sellable quantity is assumed.
    """
    if original_nominal_shares<1:
        raise ValueError("Need positive nominal share quantity")
    value=event.get("full_new_nominal_share_multiplier")
    if value is None or value<1:
        raise ValueError("Incomplete rights -> cannot report share order availability")
    eval_date=str(pd.Timestamp(day).date())
    ex=event["ex_date"]
    old=Decimal(original_nominal_shares)
    right=old*(Decimal(str(value))-Decimal(1))
    extra_listing=listing.get("new_unrestricted_shares_listing_day")
    base={
        "event_id":event["event_id"],"symbol":event["symbol"],
        "day":eval_date,"old_nominal_shares":str(old),
        "new_bonus_transfer_entitlement_shares":str(right),
        "issuer_scheduled_listing_day":extra_listing,
        "record_date":event["record_date"],"ex_date":ex,
        "this_holder_new_shares_actually_credited":broker_new_share_credit_verified,
        "realized_broker_trade_fill":False,
    }
    if eval_date<ex:
        return {**base,"new_shares_tradeable":False,
                "share_quantity_order_certified":False,
                "status":"BEFORE_EX_RIGHTS_NOT_CREDITED"}
    if not original_shares_independently_confirmed_sellable:
        return {**base,"new_shares_tradeable":False,
                "share_quantity_order_certified":False,
                "status":"OLD_SHARE_CREDIT_OR_RESTRICTION_NOT_VERIFIED"}
    if extra_listing is None:
        return {**base,"new_shares_tradeable":False,
                "share_quantity_order_certified":False,
                "status":"ISSUER_NEW_SHARES_LISTING_DATE_UNKNOWN"}
    if eval_date<extra_listing:
        return {**base,"new_shares_tradeable":False,
                "share_quantity_order_certified":False,
                "maximum_model_sellable_old_shares_only":str(old),
                "status":"ENTITLEMENT_VALUED_BUT_NEW_SHARES_NOT_LISTED"}
    if not broker_new_share_credit_verified:
        return {**base,"new_shares_tradeable":False,
                "share_quantity_order_certified":False,
                "maximum_model_sellable_old_shares_only":str(old),
                "status":"NEW_SHARES_LISTED_BUT_HOLDER_BROKER_CREDIT_UNKNOWN"}
    return {**base,"new_shares_tradeable":True,
            "share_quantity_order_certified":True,
            "maximum_model_nominal_shares_eligible_for_order":str(old+right),
            "status":"BROKER_SHARES_CREDITED_LISTED_ASK_EXTERNAL_LIMITS_AND_AUCTION"}


def audit_issuer_listing_days(catalog: dict, *, pdf_dirs: list[Path]) -> dict:
    pdfs={}
    for folder in pdf_dirs:
        for f in folder.glob("*.pdf"):
            pdfs[hashlib.sha256(f.read_bytes()).hexdigest()]=f
    verified=[]
    for event in catalog["events"]:
        if not event["complete_rights_supported_by_issuer_original"]:
            continue
        if not event["positive_stock_rights"]:
            continue
        src=pdfs.get(event["issuer_original_pdf_sha256"])
        if src is None:
            raise ValueError("Original issuer PDF hash not available")
        text="\n".join(page.extract_text() or "" for page in PdfReader(src).pages[:5])
        parsed=issuer_sse_new_share_listing_date(
            text,record=event["record_date"],ex=event["ex_date"]
        )
        verified.append({
            "symbol":event["symbol"],"event_id":event["event_id"],
            "ex_date":event["ex_date"],
            "new_nominal_share_multiplier":event["full_new_nominal_share_multiplier"],
            "original_issuer_pdf_sha256":event["issuer_original_pdf_sha256"],
            "issuer_pdf_url":event["issuer_original_pdf_url"],
            **parsed,
        })
    return {
        "kind":"EXP007_ORIGINAL_ISSUER_NEW_SHARES_LISTING_DAY_AND_SELLABILITY_GATE",
        "positive_stock_rights_full_before_listing_audit":len(verified),
        "issuer_listing_days_confirmed":sum(
            x.get("new_unrestricted_shares_listing_day") is not None for x in verified
        ),
        "unresolved_issuer_new_listing_days":sum(
            x.get("new_unrestricted_shares_listing_day") is None for x in verified
        ),
        "broker_credit_of_new_shares_observed":False,
        "orderbook_or_official_price_limit_data_included":False,
        "events":verified,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rights-catalog",type=Path,required=True)
    p.add_argument("--issuer-dirs",type=Path,nargs="+",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError(a.out)
    catalog=json.loads(a.rights_catalog.read_text("utf-8"))
    report=audit_issuer_listing_days(catalog,pdf_dirs=a.issuer_dirs)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k.startswith("issuer_") or k.startswith("positive_") or k.startswith("unresolved_")},indent=2))


if __name__=="__main__":
    main()
