"""EXP-003: verify specific historical CNINFO original PDFs and stock halts.

Do not generalize three verified dividends / one halt to full CSI300 history.
This module verifies *a pinned set of issuer documents*, cross-checks dividend
cash amounts, records document hashes, and checks a real full-day suspension
interval against independent unadjusted Eastmoney OHLCV + Qlib calendar.

Not a trading engine and not proof of auction order queue/fill.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from datetime import datetime, timezone
import time

import pandas as pd
import requests

DOCUMENTS = (
    {
        "key": "SH600340_halt_20210129",
        "symbol": "SH600340",
        "kind": "full_session_halt_start",
        "announced": "2021-01-29",
        "effective": "2021-01-29",
        "url": "https://static.cninfo.com.cn/finalpage/2021-01-29/1209209747.PDF",
        "sha256": "857f7f715e3522ace5188321156de76436d0b6d11728a990a553634eea58b703",
    },
    {
        "key": "SH600340_resume_20210219",
        "symbol": "SH600340",
        "kind": "full_session_resume_start",
        "announced": "2021-02-19",
        "effective": "2021-02-19",
        "url": "https://static.cninfo.com.cn/finalpage/2021-02-19/1209280127.PDF",
        "sha256": "3189d2e2c39a862ff2ce5669cb3d4fcb82bc6d6eb110e5e1da93a7b000e16bb8",
    },
    {
        "key": "SH600000_dividend_20210721",
        "symbol": "SH600000",
        "kind": "cash_dividend",
        "announced": "2021-07-13",
        "record_date": "2021-07-20",
        "ex_date": "2021-07-21",
        "cash_per_nominal_share_pre_tax": 0.48,
        "url": "https://static.cninfo.com.cn/finalpage/2021-07-13/1210467899.PDF",
        "sha256": "fbadb95f0d82ebe980c559cb5bf5b8d4489b2b1e9374f585704a3719c79916ba",
    },
    {
        "key": "SH600000_dividend_20220721",
        "symbol": "SH600000",
        "kind": "cash_dividend",
        "announced": "2022-07-13",
        "record_date": "2022-07-20",
        "ex_date": "2022-07-21",
        "cash_per_nominal_share_pre_tax": 0.41,
        "url": "https://static.cninfo.com.cn/finalpage/2022-07-13/1214014565.PDF",
        "sha256": "2698706b68bbd5dbff734617a816fa27dfb72bf63f9e83113b7f78baf0664b92",
    },
    {
        "key": "SZ000001_dividend_20220722",
        "symbol": "SZ000001",
        "kind": "cash_dividend",
        "announced": "2022-07-15",
        "record_date": "2022-07-21",
        "ex_date": "2022-07-22",
        "cash_per_nominal_share_pre_tax": 0.228,
        "url": "https://static.cninfo.com.cn/finalpage/2022-07-15/1214044313.PDF",
        "sha256": "3a5cbed3dfc822d6bee0f2b57dbc0da9662dce0670b92d0f6edad095d6c6de57",
    },
)

PDF_LIMIT_BYTES = 6_000_000
EASTMONEY_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("Ａ", "A").replace("Ｂ", "B")


def verify_pdf_text(document: dict, text: str) -> dict:
    """Return proof fields only when the original issuer PDF yields expected terms."""
    content = _normalized_text(text)
    if document["symbol"][2:] not in content:
        raise ValueError("Original PDF omits expected security code")
    proof = {"symbol": document["symbol"], "kind": document["kind"],
             "official_release_calendar_date": document["announced"],
             "intraday_release_timestamp_certified": False,
             "issuer_pdf_text_verified": True}
    if document["kind"] == "cash_dividend":
        if document["symbol"] == "SZ000001":
            match = re.search(r"每10股派发现金股利人民币([0-9.]+)元", content)
            if not match:
                raise ValueError("Expected 10-share dividend statement not extracted")
            amount = float(match.group(1)) / 10.0
        else:
            match = re.search(r"每股现金红利人民币([0-9.]+)元", content)
            if not match:
                raise ValueError("Expected per-share dividend statement not extracted")
            amount = float(match.group(1))
        if abs(amount - float(document["cash_per_nominal_share_pre_tax"])) > 1e-8:
            raise ValueError("PDF dividend amount does not match pinned amount")
        # The dates are verified against text, not guessed from release date.
        record = pd.Timestamp(document["record_date"])
        ex = pd.Timestamp(document["ex_date"])
        if document["symbol"] == "SZ000001":
            if not (
                f"{record.year}年{record.month}月{record.day}日" in content
                and f"{ex.year}年{ex.month}月{ex.day}日" in content
            ):
                raise ValueError("Missing official record/ex dates in PDF")
        else:
            if not (
                f"{record.year}/{record.month}/{record.day}" in content
                and f"{ex.year}/{ex.month}/{ex.day}" in content
            ):
                raise ValueError("Missing official record/ex dates in PDF")
        proof.update({
            "cash_per_nominal_share_pre_tax_pdf_confirmed": amount,
            "record_date_pdf_confirmed": document["record_date"],
            "ex_date_pdf_confirmed": document["ex_date"],
            "payout_cashflow_actual_broker_verified": False,
            "correction_or_retroactive_factor_history_known": False,
        })
    elif document["kind"] == "full_session_halt_start":
        m = re.search(r"股票将于(2021年1月29日).*?开市起停牌", content)
        if not m:
            raise ValueError("Expected suspension date absent from original PDF")
        proof["suspended_from_open_pdf_confirmed"] = "2021-01-29"
    elif document["kind"] == "full_session_resume_start":
        m = re.search(r"股票将于(2021年2月19日).*?开市起复牌", content)
        if not m:
            raise ValueError("Expected resumption date absent from original PDF")
        proof["resumed_from_open_pdf_confirmed"] = "2021-02-19"
    return proof


def fetch_pdf(session: requests.Session, doc: dict, raw_dir: Path) -> dict:
    from pypdf import PdfReader

    name = str(doc["key"])
    raw_path = raw_dir / f"{name}.pdf"
    if raw_path.exists():
        payload = raw_path.read_bytes()
    else:
        with session.get(
            doc["url"], headers={"User-Agent": "Mozilla/5.0"},
            timeout=(8, 18), stream=True,
        ) as res:
            res.raise_for_status()
            content = bytearray()
            for chunk in res.iter_content(chunk_size=256_000):
                content.extend(chunk)
                if len(content) > PDF_LIMIT_BYTES:
                    raise ValueError(f"Original announcement PDF too large: {name}")
            payload = bytes(content)
        if not payload.startswith(b"%PDF"):
            raise ValueError(f"Response is not an original PDF: {name}")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != doc["sha256"]:
        raise ValueError(f"Official PDF checksum changed: {name}")
    from io import BytesIO
    reader = PdfReader(BytesIO(payload), strict=False)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    if not text:
        raise ValueError("No extractable PDF text; abort rather than OCR guessing")
    proof = verify_pdf_text(doc, text)
    if not raw_path.exists():
        raw_path.write_bytes(payload)
    proof.update({
        "primary_document_sha256": digest,
        "primary_document_url": doc["url"],
        "primary_document_pages": len(reader.pages),
        "primary_document_bytes": len(payload),
        "text_parsed_not_OCR": True,
        "download_utc": datetime.now(timezone.utc).isoformat(),
        "original_pdf_stored_in_gitignored_local_path": True,
    })
    return proof


def fetch_independent_unadjusted_bars(
    session: requests.Session, symbol: str, start: str, end: str,
) -> tuple[pd.DataFrame, dict]:
    secid = ("1." if symbol.startswith("SH") else "0.") + symbol[2:]
    params = {
        "secid": secid, "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": 101, "fqt": 0,
        "beg": start.replace("-", ""), "end": end.replace("-", ""),
        "lmt": 150,
    }
    response = session.get(EASTMONEY_KLINE, params=params,
                           timeout=(8,18),headers={"User-Agent":"Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json()
    table = (payload.get("data") or {}).get("klines") or []
    if not table:
        raise ValueError("No independent unadjusted daily OHLCV for "+symbol)
    records = []
    for raw in table:
        fields = raw.split(",")
        if len(fields) < 7:
            raise ValueError("Unexpected independent daily bar format")
        records.append({
            "date": fields[0], "symbol": symbol,
            "open_raw": float(fields[1]), "close_raw": float(fields[2]),
            "high_raw": float(fields[3]), "low_raw": float(fields[4]),
            "volume_lots": float(fields[5]), "amount_currency": float(fields[6]),
        })
    frame = pd.DataFrame.from_records(records)
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate independent stock dates")
    return frame, {
        "source": "EASTMONEY_PUBLIC_DAILY_UNADJUSTED_BAR",
        "report_url": response.url.split("?")[0],
        "http_status": response.status_code,
        "response_body_sha256": hashlib.sha256(response.content).hexdigest(),
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "volume_unit": "100 shares per lot (A share normal lot)",
        "not_auction_depth": True, "not_actual_order_fill": True,
    }


def verify_official_suspension_with_bar_calendar(
    *, suspension_from: str, resume_from: str,
    bars: pd.DataFrame, exchange_calendar: pd.DatetimeIndex,
) -> dict:
    """Verify all exchange sessions during the announced halt lack daily bars."""
    stop, resume = pd.Timestamp(suspension_from), pd.Timestamp(resume_from)
    dates = pd.DatetimeIndex(exchange_calendar).normalize()
    halted = dates[(dates >= stop) & (dates < resume)]
    observed = set(pd.to_datetime(bars["date"]).dt.normalize().tolist())
    if not len(halted):
        raise ValueError("Empty official suspension interval")
    violation = [d for d in halted if d in observed]
    if violation:
        raise ValueError("Daily bar appeared during officially halted interval")
    if resume not in observed:
        raise ValueError("No independent bar on official resume date")
    resumed = bars.loc[pd.to_datetime(bars.date).eq(resume)]
    if not (resumed["volume_lots"].gt(0).all()
            and resumed["open_raw"].gt(0).all()):
        raise ValueError("Invalid opening/volume on resume date")
    return {
        "symbol": "SH600340",
        "official_halted_from": suspension_from,
        "official_resume_from": resume_from,
        "halted_exchange_sessions_confirmed": int(len(halted)),
        "independent_daily_bar_during_halt": len(violation),
        "independent_resume_date_traded_volume_positive": True,
        "secondary_market_feed": "Eastmoney raw daily OHLCV",
        "daily_evidence_proves_no_trades_in_halt_period": True,
        "intraday_auction_fill_probability_known": False,
        "orderbook_queue_data_available": False,
    }


def run(output: Path, *, qlib_calendar_path: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite evidence folder: {output}")
    output.mkdir(parents=True, exist_ok=False)
    raw_dir = output/"raw_official_pdfs"
    raw_dir.mkdir()
    records = []
    with requests.Session() as session:
        for doc in DOCUMENTS:
            record = fetch_pdf(session, doc, raw_dir)
            records.append(record)
            print("VERIFIED",doc["key"],record["primary_document_sha256"],flush=True)
            time.sleep(0.2)
        bars, bar_source = fetch_independent_unadjusted_bars(
            session, "SH600340", start="2021-01-15", end="2021-03-05"
        )
    bars.to_csv(output/"SH600340_unadjusted_bars.csv",index=False)
    calendar = pd.DatetimeIndex(pd.read_csv(
        qlib_calendar_path,header=None,names=["date"]
    )["date"]).normalize()
    halt_proof = verify_official_suspension_with_bar_calendar(
        suspension_from="2021-01-29", resume_from="2021-02-19",
        bars=bars, exchange_calendar=calendar,
    )
    result = {
        "source_class": "OFFICIAL_PDF_DIRECT_CONTENT_AND_SECONDARY_HISTORICAL_OHLCV",
        "verified_documents": records,
        "halt_primary_secondary_corroboration": halt_proof,
        "independent_bar_request": bar_source,
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "official_intraday_publication_time_certified": False,
        "dividend_amounts_pdf_confirmed_for_pinned_three_events": True,
        "full_CSI300_dividend_actions_PDF_confirmed": False,
        "all_securities_historical_exchange_limit_prices_available": False,
        "all_securities_historical_auction_depth_available": False,
        "realized_broker_fill_evidence_available": False,
    }
    (output/"primary_evidence_report.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--qlib-calendar",type=Path,required=True)
    args=p.parse_args()
    result=run(args.output,qlib_calendar_path=args.qlib_calendar)
    print(json.dumps({
        "documents": len(result["verified_documents"]),
        "halted_exchange_sessions": (
            result["halt_primary_secondary_corroboration"]
            ["halted_exchange_sessions_confirmed"]
        ),
        "official_pdf_amounts_verified": 3,
        "market_auction_fills_verified": False,
    },indent=2))


if __name__=="__main__":
    main()
