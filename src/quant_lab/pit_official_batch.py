"""Targeted batch audit of issuer-origin corporate-action implementation PDFs.

This does not turn an unversioned provider history into a PIT-vintage series.
We separate official *document bytes + day*, cash amounts parsed from text,
and third-party record/ex dates. PDF text parsing is conservative; no OCR or
guessing where the original PDF is scanned or has ambiguous amounts.

Documents and source responses remain in locally gitignored data/pit/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import time

import pandas as pd
import requests

from .pit_collect import fetch_cninfo

PDF_MAX_BYTES = 8_000_000
VALID_TITLE_WORDS = ("权益分派", "分红派息", "利润分配", "红利派发")
MONEY_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
SH_PER_SHARE = re.compile(
    r"(?:A股)?每股现金(?:红利|股利)(?:人民币)?([0-9]+(?:\.[0-9]+)?)元"
)
TEN_SHARE = (
    re.compile(r"每10股(?:派发|派送|派现|派)?现金(?:红利|股利)?(?:人民币)?([0-9]+(?:\.[0-9]+)?)元"),
    re.compile(r"每10股(?:派发|派送|派现|派)?(?:人民币)?([0-9]+(?:\.[0-9]+)?)元"),
    re.compile(r"每10股(?:派发)?(?:税前)?现金股利人民币([0-9]+(?:\.[0-9]+)?)元"),
)


def compact(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    return text.translate(str.maketrans({
        "０":"0", "１":"1", "２":"2", "３":"3", "４":"4",
        "５":"5", "６":"6", "７":"7", "８":"8", "９":"9",
        "．":".", "Ａ":"A", "Ｂ":"B",
    }))


def extract_cash_candidates_per_share(document_text: str) -> list[float]:
    """Only explicit per-share / per-ten-share RMB cash-dividend statements."""
    t = compact(document_text)
    out = []
    for m in SH_PER_SHARE.finditer(t):
        out.append(float(m.group(1)))
    for rex in TEN_SHARE:
        for m in rex.finditer(t):
            out.append(float(m.group(1)) / 10.0)
    # Avoid duplicate string occurrences of same number, but different
    # announced amounts are not 'resolved' automatically.
    return sorted(set(round(v, 9) for v in out if 0 <= v <= 200))



# Only tax-inclusive phrases explicitly associated with a per-share/ten-share
# gross cash amount are eligible for automatic corporate action accounting.
# The same PDF often states a SECOND amount after "扣税后" (net of taxes); that
# number must never be mistaken for the gross pre-tax cash entitlement.
TAX_INCLUSIVE_PATTERNS = (
    (re.compile(r"每股(?:派发)?现金(?:红利|股息|股利)?(?:人民币)?([0-9]+(?:\.[0-9]+)?)元.{0,10}?含税"), 1.0),
    (re.compile(r"每10股(?:派发|派送|派现|派)?(?:现金(?:红利|股利)?|人民币)?(?:人民币)?([0-9]+(?:\.[0-9]+)?)元(?:人民币)?(?:现金)?[（(].{0,15}?含税"), .1),
    (re.compile(r"每10股派人民币([0-9]+(?:\.[0-9]+)?)元现金[（(].{0,15}?含税"), .1),
    (re.compile(r"每10股派发现金红利[（(]含税[）)]人民币([0-9]+(?:\.[0-9]+)?)元"), .1),
)


def extract_explicit_pretax_cash_per_share(document_text: str) -> list[float]:
    """PDF-only, strict pre-tax/tax-inclusive source amount candidates.

    If multiple distinct gross values remain, DO NOT silently select the
    amount nearest to a third-party aggregator record.
    """
    text=compact(document_text)
    candidates=[]
    for rex,scale in TAX_INCLUSIVE_PATTERNS:
        for m in rex.finditer(text):
            candidates.append(round(float(m.group(1))*scale, 9))
    return sorted({x for x in candidates if 0 <= x <= 200})


def strict_cash_match(candidates: list[float], thirdparty_expected: float | None) -> dict:
    if thirdparty_expected is None:
        if not candidates:
            status="PDF_NUMBER_UNEXTRACTABLE"
        elif len(candidates)>1:
            status="PDF_MULTI_AMOUNT_NEEDS_MANUAL_REVIEW"
        else:
            status="OFFICIAL_PDF_NUMBER_ONLY_NOT_RECONCILED"
        return {
            "status": status,
            "official_distinct_cash_per_share_candidates": candidates,
            "cash_per_share_verified": (
                candidates[0] if len(candidates)==1 else None
            ),
        }
    if not candidates:
        return {
            "status": "PDF_NUMBER_UNEXTRACTABLE",
            "official_distinct_cash_per_share_candidates": [],
            "cash_per_share_verified": None,
        }
    hits = [v for v in candidates if abs(v - thirdparty_expected) < 1e-6]
    return {
        "status": ("PDF_CASH_MATCHED_TO_THIRDPARTY"
                   if len(hits) == 1 and len(candidates)==1
                   else ("PDF_MULTI_AMOUNT_NEEDS_MANUAL_REVIEW"
                         if len(candidates)>1 else "PDF_CASH_MISMATCH")),
        "official_distinct_cash_per_share_candidates": candidates,
        "cash_per_share_verified": hits[0] if len(candidates)==1 and len(hits)==1 else None,
    }


def is_issuer_dividend_implementation(title: str) -> bool:
    """Require a *standalone* issuer implementation disclosure, not a bond or
    buyback notice merely referring to a completed distribution.

    Deliberately conservative. Unrecognized legitimate titles are marked for
    manual review, not added as verified dividends.
    """
    clean=compact(title.replace("<em>","").replace("</em>",""))
    # Some original issuer implementation PDF titles include a literal
    # "A股" insertion or a trailing official announcement identifier.
    # Strip only an identifier of the form (2021-123), not arbitrary words.
    clean=re.sub(r"[（(]20\d{2}[-－]\d+[）)]$", "", clean)
    return bool(re.search(
        r"(?:权益分派(?:A股)?|分红派息|利润分配|现金分红)实施公告$",
        clean
    ))


def _get_doc(session: requests.Session, url: str, path: Path) -> tuple[bytes, str]:
    if path.is_file():
        pdf = path.read_bytes()
    else:
        r = session.get(url, headers={"User-Agent":"Mozilla/5.0"},
                        timeout=(7, 18), stream=True)
        r.raise_for_status()
        content = bytearray()
        for block in r.iter_content(131072):
            content.extend(block)
            if len(content) > PDF_MAX_BYTES:
                raise ValueError("Issuer PDF exceeds bounded size")
        pdf = bytes(content)
        if not pdf.startswith(b"%PDF"):
            raise ValueError("Issuer PDF response is not a PDF")
        path.write_bytes(pdf)
    if not pdf.startswith(b"%PDF"):
        raise ValueError("Cached content is not PDF")
    return pdf, hashlib.sha256(pdf).hexdigest()


def _thirdparty_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    obj=json.loads(path.read_text(encoding="utf-8"))
    return [x for x in obj.get("events",[]) if x.get("implementation_announcement_date")
            and x.get("ex_date")]


def verify_single_document(*, doc: dict, thirdparty: list[dict],
                           session: requests.Session,
                           raw_dir: Path) -> dict:
    from pypdf import PdfReader

    sym=doc["symbol"]
    day=doc["published_calendar_date"]
    title=doc["announcement_title"]
    if not is_issuer_dividend_implementation(title):
        raise ValueError("Unrelated PDF title rejected")
    if not doc["pdf_url"].startswith("https://static.cninfo.com.cn/finalpage/"):
        raise ValueError("Nonofficial PDF URL rejected")
    label=doc["announcement_id"] or hashlib.sha256(doc["pdf_url"].encode()).hexdigest()[:14]
    dest=raw_dir/f"{sym}_{day}_{label}.pdf"
    payload,digest=_get_doc(session,doc["pdf_url"],dest)
    pdf=PdfReader(BytesIO(payload),strict=False)
    parsed="\n".join(p.extract_text() or "" for p in pdf.pages[:4])
    text=compact(parsed)
    if sym[2:] not in text:
        raise ValueError("Issuer PDF lacks expected stock code")
    if not text:
        raise ValueError("Scanned/unparsable document; no OCR claim")
    candidates=extract_cash_candidates_per_share(text)
    pretax_candidates=extract_explicit_pretax_cash_per_share(text)
    matches=[x for x in thirdparty
             if x["implementation_announcement_date"]==day]
    expected=float(matches[0]["cash_per_share_pre_tax"]) if len(matches)==1 else None
    # Restrict automatic matching to explicit tax-inclusive gross amounts.
    # Only if no pre-tax context exists, fall back to the original ambiguous
    # candidate set (which may be rejected for containing net-of-tax amounts).
    amount=strict_cash_match(
        pretax_candidates if pretax_candidates else candidates, expected
    )
    if len(matches)>1:
        amount["status"]="MULTIPLE_THIRDPARTY_EVENTS_SAME_ANNOUNCEMENT_DAY"
        amount["cash_per_share_verified"]=None

    dated_match=False
    if len(matches)==1:
        ex=pd.Timestamp(matches[0]["ex_date"])
        reg=pd.Timestamp(matches[0]["record_date"])
        # Requiring source text to include the exact dates is stronger than
        # matching only index metadata. Actual payment day is a separate field.
        ex_terms=[f"{ex.year}/{ex.month}/{ex.day}",
                  f"{ex.year}年{ex.month}月{ex.day}日"]
        reg_terms=[f"{reg.year}/{reg.month}/{reg.day}",
                   f"{reg.year}年{reg.month}月{reg.day}日"]
        dated_match=(any(s in text for s in ex_terms)
                     and any(s in text for s in reg_terms))
    result={
        "symbol":sym,"official_notice_day":day,"issuer_pdf_url":doc["pdf_url"],
        "issuer_pdf_sha256":digest,"bytes":len(payload),
        "document_pages":len(pdf.pages),
        "issuer_pdf_text_extractable":True,
        "official_announcement_title":title,"announcement_id":doc["announcement_id"],
        "intraday_announcement_time_certified":False,
        "thirdparty_same_day_events":len(matches),
        "thirdparty_ex_date":matches[0]["ex_date"] if len(matches)==1 else None,
        "thirdparty_record_date":matches[0]["record_date"] if len(matches)==1 else None,
        "thirdparty_per_share_pretax":expected,
        "issuer_pdf_all_cash_amount_candidates":candidates,
        "issuer_pdf_explicit_tax_inclusive_cash_candidates":pretax_candidates,
        "gross_amount_context_used":bool(pretax_candidates),
        "issuer_pdf_ex_record_date_literals_both_present":dated_match,
        "payment_and_broker_cash_posting_certified":False,
        "publisher_adjustment_factor_historical_vintage_certified":False,
        "raw_pdf_kept_locally_not_committed":True,
        **amount,
    }
    if result["status"]=="PDF_CASH_MATCHED_TO_THIRDPARTY" and not dated_match:
        result["status"]="PDF_CASH_MATCHED_DATES_NOT_CONFIRMED"
    return result


def run_batch(symbols:list[str], *, event_root:Path,
              recovered_root:Path|None, output:Path,
              delay:float=.55, max_docs_per_symbol:int=3) -> dict:
    if output.exists():
        raise FileExistsError("Results directory already exists; never overwrite audit")
    if delay < .3:
        raise ValueError("Minimum issuer-request pacing is 0.3 seconds")
    output.mkdir(parents=True)
    raw_dir=output/"issuer_pdfs"
    raw_dir.mkdir()
    records,failures,issuer_fetch_log=[],[],[]
    with requests.Session() as sess:
        for i,sym in enumerate(symbols,1):
            try:
                official=None
                if recovered_root and (recovered_root/f"{sym}.json").exists():
                    record=json.loads((recovered_root/f"{sym}.json").read_text("utf-8"))
                    if record.get("result")=="OFFICIAL_INDEX_SEARCH":
                        official=record.get("relevant_pdf_records")
                if official is None:
                    official,requests_meta=fetch_cninfo(sess,sym,include_trading=False)
                    issuer_fetch_log.extend(requests_meta)
                relevant=[r for r in official
                          if is_issuer_dividend_implementation(r["announcement_title"])
                          and "2021-" <= r["published_calendar_date"] <= "2022-12-31"]
                relevant.sort(key=lambda x:(x["published_calendar_date"],x["announcement_id"]))
                thirdparty=_thirdparty_events(event_root/f"{sym}.json")
                for doc in relevant[:max_docs_per_symbol]:
                    try:
                        result=verify_single_document(
                            doc=doc,thirdparty=thirdparty,session=sess,
                            raw_dir=raw_dir,
                        )
                        records.append(result)
                        print(i,len(symbols),sym,result["official_notice_day"],
                              result["status"],result["cash_per_share_verified"],flush=True)
                    except Exception as exc:
                        failures.append({"symbol":sym,"announcement_id":doc.get("announcement_id"),
                                         "stage":"issuer_pdf","type":type(exc).__name__,
                                         "reason":str(exc)[:320]})
                        print(i,len(symbols),sym,"PDF_FAILED",
                              type(exc).__name__,str(exc)[:100],flush=True)
                    time.sleep(delay)
                if not relevant:
                    failures.append({"symbol":sym,"stage":"official_index_search",
                                     "reason":"no exact dividend implementation PDF matches limited official title/date keywords"})
                    print(i,len(symbols),sym,"NO_OFFICIAL_IMPLEMENTATION_PDF",flush=True)
            except Exception as exc:
                failures.append({"symbol":sym,"stage":"query",
                                 "type":type(exc).__name__,"reason":str(exc)[:320]})
                print(i,len(symbols),sym,"INDEX_ERROR",type(exc).__name__,
                      str(exc)[:100],flush=True)
            time.sleep(delay)
    summary={
        "kind":"LIMITED_TARGETED_OFFICIAL_ISSUER_PDF_AUDIT",
        "source":"CNINFO official original issuer PDF",
        "period":["2021-01-01","2022-12-31"],
        "targeted_symbols":symbols,
        "n_symbols_targeted":len(symbols),
        "n_pdf_records":len(records),
        "n_cash_amounts_and_dates_crossmatched":sum(
            x["status"]=="PDF_CASH_MATCHED_TO_THIRDPARTY" for x in records
        ),
        "n_cash_amounts_crossmatched_but_date_uncertain":sum(
            x["status"]=="PDF_CASH_MATCHED_DATES_NOT_CONFIRMED" for x in records
        ),
        "n_primary_cash_amount_only_without_vendor_crossmatch":sum(
            x["status"]=="OFFICIAL_PDF_NUMBER_ONLY_NOT_RECONCILED"
            and x["cash_per_share_verified"] is not None for x in records
        ),
        "n_unresolved_source_or_extraction_failures":len(failures),
        "documents":records,"failures":failures,"cninfo_requests":issuer_fetch_log,
        "scope_limitation":"not representative of all 738 vendor events; targeted fixed symbol sample only",
        "historical_announcements_calendar_day_only":True,
        "exact_intraday_release_time_certified":False,
        "historical_factor_version_certified":False,
        "current_dividends_are_not_applied_to_adjusted_qlib_proxy_returns":True,
    }
    (output/"issuer_batch_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+",required=True)
    p.add_argument("--event-root",type=Path,required=True)
    p.add_argument("--recovered-root",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--delay",type=float,default=.55)
    args=p.parse_args()
    report=run_batch(sorted(set(args.symbols)),event_root=args.event_root,
                     recovered_root=args.recovered_root,output=args.out,
                     delay=args.delay)
    print(json.dumps({
        "targeted":report["n_symbols_targeted"],
        "pdfs":report["n_pdf_records"],
        "cash_amount_and_both_dates_verified":report["n_cash_amounts_and_dates_crossmatched"],
        "cash_amount_vendor_verified_dates_uncertain":report["n_cash_amounts_crossmatched_but_date_uncertain"],
        "cash_only_missing_vendor":report["n_primary_cash_amount_only_without_vendor_crossmatch"],
        "failures":report["n_unresolved_source_or_extraction_failures"],
    },indent=2))


if __name__=="__main__":
    main()
