"""EXP-009: source-hashed issuer exchange notice and two original fund report proofs.

Do NOT turn retrospective fund semiannual disclosures (issued Aug 2021)
into *information available on the June 2021 decision dates*. They offer
high-quality independent corroboration of a suspension **after the fact**:
  - June 16 SZSE original HTML notice confirms open-start halt but leaves
    resumption contingent on later issuer disclosure;
  - June 30 broker's dated notice still has blank resume field;
  - TWO independent fund managers' original 2021 semiannual filings, first
    published Aug 27/Aug 31, disclose the effective start June 16,
    actual resume July 6, interim fair value 5.59 and restart open 6.15.
They do NOT prove the first five sessions ended as a separate corporate
event on June 22. This module cannot reclassify existing original-issuer
134/139 PRIMARY evidence as 139/139 primary. It creates a separate
retrospective multi-source evidence tier, without changing any model PnL.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader


STOCK = "SZ002024"
STOCK_CODE = "002024"
TARGET_START = "2021-06-16"
ACTUAL_RESUME = "2021-07-06"
BROKER_DATE = "2021-06-30"
TARGET_MARK = 5.59
RESTART_OPEN = 6.15
SOURCES = {
    "exchange": {
        "name": "Shenzhen Stock Exchange",
        "file": "szse_002024_halt_20210616.html",
        "sha256": "52670239516bcf63914d7111ceb722985f17eba196c0e14a390cfd68a00be3d3",
        "url": "https://www.szse.cn/disclosure/notice/t20210616_586435.html",
        "publication_day": "2021-06-16",
        "kind": "PRIMARY_EXCHANGE_INITIAL_HALT_START_ONLY",
    },
    "broker": {
        "name": "Cinda Securities",
        "file": "broker_20210630.html",
        "sha256": "4c29ccffe3feeeded19247c1b0d6d153364d76f4b22928e47d078effe8c9c2ee",
        "url": "https://www.cindasc.com/osoa/views/a/20210630/43370.html",
        "publication_day": "2021-06-30",
        "kind": "SECONDARY_BROKER_DATED_HALT_START_RESUME_BLANK",
    },
    "fund1": {
        "name": "融通深证100指数证券投资基金",
        "manager": "融通基金管理有限公司",
        "file": "rt_shenzhen100_2021_interim.pdf",
        "sha256": "3baaf3c769ab8def9f4228019711c8704ea87776e212a3d30defa36a2c1c5322",
        "url": "https://pdf.dfcfw.com/pdf/H2_AN202108271512608109_1.pdf",
        "publication_day": "2021-08-27",
        "asof_day": "2021-06-30",
        "reported_shares": 1_900_511,
        "reported_stock_mark": 10_623_856.49,
        "kind": "ORIGINAL_FUND_INTERIM_PDF_RETRIEVED_FROM_PUBLIC_MIRROR",
    },
    "fund2": {
        "name": "中科沃土沃嘉灵活配置混合型证券投资基金",
        "manager": "中科沃土基金管理有限公司",
        "file": "zk_wojia_2021_interim.pdf",
        "sha256": "3477978651fc3ec8e881c389c3c65164acaf50c10cfe3e310955748fff359f0f",
        "url": "https://pdf.dfcfw.com/pdf/H2_AN202108311513451275_1.pdf",
        "publication_day": "2021-08-31",
        "asof_day": "2021-06-30",
        "reported_shares": 31_900,
        "reported_stock_mark": 178_321.00,
        "kind": "ORIGINAL_FUND_INTERIM_PDF_RETRIEVED_FROM_PUBLIC_MIRROR",
    },
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("Ａ", "A")


def sha256_file(path: Path, expected: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Missing pinned source document: {path}")
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != expected:
        raise ValueError(f"Original source SHA256 mismatch for {path.name}")
    return got


def verify_exchange_original(html: str) -> dict:
    document = BeautifulSoup(html, "html.parser")
    txt = normalize(document.get_text(" ", strip=True))
    required = [
        "深圳证券交易所", "2021-06-16", "苏宁易购",
        "证券代码：002024", "2021年6月16日开市起临时停牌",
        "待公司通过指定媒体披露相关公告后复牌",
    ]
    if not all(s in txt for s in required):
        raise ValueError("Primary SZSE announcement does not verify exact initial halt")
    return {
        "symbol": STOCK,
        "publisher": "SHENZHEN_STOCK_EXCHANGE",
        "publication_day": "2021-06-16",
        "initial_full_session_halt_from": TARGET_START,
        "resume_effective_date_given": None,
        "evidence_grade": "PRIMARY_EXCHANGE_HALT_START_ONLY",
        "usable_from_original_publication_day": True,
        "exact_intraday_notice_publication_certified": False,
    }


def verify_broker_original(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for tr in soup.find_all("tr"):
        cols = [tag.get_text(" ", strip=True) for tag in tr.find_all(["th", "td"])]
        if any(re.fullmatch(r"002024[.]sz", x.strip(), re.I) for x in cols):
            found.append(cols)
    if len(found) != 1:
        raise ValueError("Broker security table has no unique ticker row")
    row = found[0]
    if (len(row) < 6 or "苏宁易购" not in "".join(row)
            or "2021-06-16 09:30:00" not in row
            or row[4].strip() != ""
            or "临时停牌" not in row):
        raise ValueError("Historical broker stock halt/resume fields disagree")
    all_text = normalize(soup.get_text(" ", strip=True))
    if "2021-6-30" not in all_text and "2021年6月30日" not in all_text:
        raise ValueError("Broker notice historical publication day missing")
    return {
        "symbol": STOCK,
        "publisher": "CINDA_SECURITIES_BROKER",
        "publication_day": BROKER_DATE,
        "historical_halt_start": TARGET_START,
        "resume_time": None,
        "evidence_grade": "SECONDARY_DATED_BROKER_NO_RESUME_TIME",
        "does_not_establish_actual_resume_day": True,
    }


def verify_fund_text(first_page: str, suspended_holdings_page: str,
                     *, expected: dict) -> dict:
    cover = normalize(first_page)
    text = normalize(suspended_holdings_page)
    fund_name = normalize(expected["name"])
    manager = normalize(expected["manager"])
    yyyy, mm, dd = expected["publication_day"].split("-")
    published = f"送出日期：{int(yyyy)}年{int(mm)}月{int(dd)}日"
    if not all(k in cover for k in (
        fund_name, manager, "2021年中期报告",
        "2021年6月30日", published
    )):
        raise ValueError("Independent fund original cover/manager/publication mismatch")
    section = "6.4.12.2期末持有的暂时停牌等流通受限股票"
    if section not in text:
        raise ValueError("Suspended holdings original section missing")
    start = text.find("002024苏宁易购")
    if start < 0 or text.find("002024苏宁易购", start+1) >= 0:
        raise ValueError("Not a unique original fund suspended-stock row")
    # The table has fixed columns date/reason/fair-value/actual-resume/open/
    # fund share position/cost/fair-value. Reconstituted line breaks are
    # normalized for layout, but other row values aren't substituted.
    row = text[start:start+420]
    pattern = (
        r"^002024苏宁易购2021年6月16日"
        r"(?:临时停牌|重大事项停牌)"
        r"5[.]592021年7月6日6[.]15"
        r"([\d,]+)([\d,.]+)"
    )
    match = re.match(pattern, row)
    if match is None:
        raise ValueError("Original fund table did not corroborate halt/resume and prices")
    shares = int(match.group(1).replace(",", ""))
    if shares != expected["reported_shares"]:
        raise ValueError("Independent fund share count disagrees")
    implied_mark = round(shares * TARGET_MARK, 2)
    if abs(implied_mark - expected["reported_stock_mark"]) > 0.011:
        raise ValueError("Original fund stock valuation arithmetic differs")
    if expected["publication_day"] <= ACTUAL_RESUME:
        raise ValueError("Cannot claim fund knew future resumption before its actual disclosure")
    return {
        "symbol": STOCK,
        "fund_manager": expected["manager"],
        "fund_name": expected["name"],
        "original_report_publication_day": expected["publication_day"],
        "original_period_end": expected["asof_day"],
        "historical_halt_start_reported": TARGET_START,
        "eventual_actual_resume_reported": ACTUAL_RESUME,
        "halted_share_mark_at_2021_06_30": TARGET_MARK,
        "reported_resumption_open": RESTART_OPEN,
        "fund_reported_nominal_shares": shares,
        "fund_reported_total_mark": expected["reported_stock_mark"],
        "fund_mark_math_verified": True,
        "retrospectively_reported_after_resume": True,
        "not_historical_decision_day_observable": True,
        "not_actual_order_fill": True,
        "evidence_grade": "ORIGINAL_FUND_PERIODIC_DISCLOSURE_RETROSPECTIVE",
    }


def verified_fund_pages(path: Path, expected: dict) -> tuple[dict, list[int]]:
    document = PdfReader(path, strict=False)
    first = document.pages[0].extract_text() or ""
    matches = [
        i for i, page in enumerate(document.pages)
        if "002024" in (page.extract_text() or "")
        and "停牌" in (page.extract_text() or "")
        and "6.4.12.2" in (page.extract_text() or "")
    ]
    if len(matches) != 1:
        raise ValueError("Cannot determine a unique original suspended holdings page")
    target = document.pages[matches[0]].extract_text() or ""
    result = verify_fund_text(first, target, expected=expected)
    return result, matches


def audit_sources(*, fund_root: Path, broker_file: Path,
                  prior_exp008_report: dict, historical: pd.DataFrame,
                  exchange_calendar: list[str]) -> dict:
    if prior_exp008_report.get("kind") != (
        "EXP008_ISSUER_ORIGINAL_EXTRA_UNRESOLVED_PRICE_GAP_PROOFS"
    ):
        raise ValueError("Source must be a frozen EXP-008 original issuer report")
    if (prior_exp008_report["total_issuer_documented_halt_stock_days"] != 134
            or prior_exp008_report["still_missing_original_verified_stoppage_or_resume_source"] != 5):
        raise ValueError("Don't replace original 134/139 verification with a new source threshold")
    prior_missing = {
        (x["symbol"], x["date"])
        for x in prior_exp008_report["remaining_unverified_stock_days"]
    }
    dates = sorted(set(str(pd.Timestamp(s).date()) for s in exchange_calendar))
    expected_days = {
        (STOCK, day) for day in dates
        if "2021-06-16" <= day <= "2021-06-22"
    }
    if len(expected_days) != 5 or prior_missing != expected_days:
        raise ValueError("These 5 issuer-unresolved stock/calendar keys have changed")
    stock = historical.loc[
        historical["asset"].eq(STOCK)
        & historical["date"].between("2021-06-16", "2021-06-22")
    ]
    actual = {
        (str(x.asset), str(pd.Timestamp(x.date).date()))
        for x in stock.itertuples(index=False)
        if bool(x.index_member_asof) and not bool(x.known_close_t)
    }
    if actual != expected_days:
        raise ValueError("Some retrospective suspended days have a Qlib positive bar or absent membership")
    exchange_spec = SOURCES["exchange"]
    sha256_file(fund_root/exchange_spec["file"],exchange_spec["sha256"])
    exchange = verify_exchange_original(
        (fund_root/exchange_spec["file"]).read_text("utf-8", errors="replace")
    )
    broker = SOURCES["broker"]
    sha256_file(broker_file, broker["sha256"])
    broker_proof = verify_broker_original(
        broker_file.read_text("utf-8", errors="replace")
    )
    fund_proofs = []
    for key in ("fund1", "fund2"):
        source = SOURCES[key]
        file=fund_root/source["file"]
        sha256_file(file,source["sha256"])
        proof,pages=verified_fund_pages(file,source)
        proof.update({
            "source_url":source["url"],
            "original_fund_pdf_sha256":source["sha256"],
            "original_report_halted_stock_table_pdf_zero_indexed_page":pages[0],
            "original_fund_pdf_pages":len(PdfReader(file,strict=False).pages),
        })
        fund_proofs.append(proof)
    managers={x["fund_manager"] for x in fund_proofs}
    if len(managers)!=2:
        raise ValueError("Fund reports are not from independent managers")
    if any(x["eventual_actual_resume_reported"]!=ACTUAL_RESUME
           or x["historical_halt_start_reported"]!=TARGET_START
           or x["halted_share_mark_at_2021_06_30"]!=TARGET_MARK
           for x in fund_proofs):
        raise ValueError("Two fund originals do not agree about old trading halt")
    return {
        "kind":"EXP009_SUNING_FIVE_REMAINING_MEMBER_DAY_SECONDARY_ORIGINAL_FUND_CORROBORATION",
        "frozen_qlib_unavailable_member_days_total":139,
        "original_issuer_or_exchange_FULL_interval_verified_days_retained":134,
        "new_additional_fund_original_retrospective_only_corrob_days":5,
        "total_member_days_with_original_primary_interval_or_independent_fund_retrospective_evidence":139,
        "primary_original_issuer_first_five_day_segment_end_date_still_unverified":True,
        "official_exchange_halt_start_proven":True,
        "official_exchange_ended_first_segment_on_2021_06_22":False,
        "fund_original_disclosure_count":len(fund_proofs),
        "independent_original_fund_managers":sorted(managers),
        "fund_disclosure_dates_after_halt_and_resume":True,
        "all_five_original_Qlib_stock_days_without_positive_price":True,
        "five_additional_retrospectively_corrob_stock_days":sorted([
            {"symbol":s,"date":d,"grade":"TWO_FUND_PERIODIC_ORIGINAL_DISCLOSURES_RETROSPECTIVE"}
            for s,d in expected_days
        ],key=lambda x:x["date"]),
        "primary_exchange_source":{
            **exchange,
            "source_url":exchange_spec["url"],
            "original_html_sha256":exchange_spec["sha256"],
        },
        "dated_broker_source":{
            **broker_proof,
            "source_url":broker["url"],
            "original_html_sha256":broker["sha256"],
        },
        "fund_original_report_proofs":fund_proofs,
        "realized_broker_fills_verified":False,
        "complete_day_by_day_exchange_halt_status_archive_verified":False,
        "actual_limit_up_down_security_day_prices_verified":False,
        "publication_time_hindsight_guard":"funds issued Aug 27/31 2021, hence cannot be treated as decision-day inputs in June 2021",
        "old_model_predictions_or_returns_changed":False,
        "interpretation":"134/139 original issuer exact-interval evidence + five independent original fund-periodic retrospective corroborations. NOT 139/139 primary exchange halt certificates, nor proof that the first issuer reason-specific segment ended June22. Broker blank resume preserved.",
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-funds-and-exchange-dir",type=Path,required=True)
    p.add_argument("--broker-original-html",type=Path,required=True)
    p.add_argument("--prior-exp008",type=Path,required=True)
    p.add_argument("--historical-panel",type=Path,required=True)
    p.add_argument("--calendar",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    if x.out.exists():
        raise FileExistsError("Cannot overwrite prior experiment source grade or result")
    prior=json.loads(x.prior_exp008.read_text("utf8"))
    frame=pd.read_parquet(x.historical_panel,
                          columns=["asset","date","index_member_asof","known_close_t"])
    dates=pd.read_csv(x.calendar,header=None)[0].astype(str).tolist()
    report=audit_sources(
        fund_root=x.original_funds_and_exchange_dir,
        broker_file=x.broker_original_html,
        prior_exp008_report=prior,
        historical=frame,
        exchange_calendar=dates
    )
    report["generated_at_utc"]=datetime.now(timezone.utc).isoformat()
    x.out.parent.mkdir(parents=True, exist_ok=True)
    x.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                     encoding="utf-8")
    print(json.dumps({
        key:report[key] for key in (
            "original_issuer_or_exchange_FULL_interval_verified_days_retained",
            "new_additional_fund_original_retrospective_only_corrob_days",
            "total_member_days_with_original_primary_interval_or_independent_fund_retrospective_evidence",
            "fund_original_disclosure_count",
            "primary_original_issuer_first_five_day_segment_end_date_still_unverified",
        )
    },indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
