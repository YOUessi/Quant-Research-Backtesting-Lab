"""Bounded, restartable public-data collector for historical corporate actions.

- Eastmoney RPT_SHAREBONUS_DET: implementation/plan, record and ex dates,
  per-10 shares/cash terms; an unversioned 2026 source snapshot.
- CNINFO: original official disclosure index, day/time metadata and PDF URLs.
  We match the official *calendar date and title* only; dividend amounts
  remain third-party until PDF text / issuer statement is audited.
- Returns a local gitignored evidence cache with content hashes. No tokens,
  no hidden APIs, no data redistribution, no trading-availability claims.

Uses ordinary public interfaces conservatively. 429/403 is a real failure;
never bypass site restrictions. Company shareholding and other private data
are not requested.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import pandas as pd
import requests

from .pit_events import (
    attach_official_announcement, normalise_cninfo_announcements,
    normalise_eastmoney_dividends, qlib_symbol,
)

EM_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
CN_ORG_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"
CN_NOTICE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
USER_AGENT = "QuantResearchBacktestingLab/0.1 (academic source provenance; low rate)"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; QuantResearchBacktestingLab/0.1)",
    "Accept": "application/json, text/plain, */*",
}


def sha_content(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch_json(session: requests.Session, *, url: str,
               params: dict, post: bool = False) -> tuple[dict | list, dict]:
    """Request and validate JSON once; do not hide HTTP failures as empty data."""
    response = session.request(
        "POST" if post else "GET", url,
        data=params if post else None,
        params=None if post else params,
        headers={**HEADERS, **({"Referer": "https://www.cninfo.com.cn/"}
                               if "cninfo" in url else {})},
        timeout=(7, 18),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, (dict, list)):
        raise ValueError("Unexpected non-object JSON from public data provider")
    return payload, {
        "url": response.url.split("?")[0],
        "request_args": params,
        "http_status": response.status_code,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "body_sha256": sha_content(response.content),
        "body_bytes": len(response.content),
        "content_type": response.headers.get("content-type"),
        "source_level": (
            "OFFICIAL_DISCLOSURE_INDEX" if "cninfo.com.cn" in url
            else "THIRD_PARTY_DIVIDEND_AGGREGATOR"
        ),
    }


def _symbol(s: str) -> str:
    return qlib_symbol(s)


def historical_csi300_union(instrument_file: Path, *,
                            first="2021-01-04", last="2022-12-30") -> list[str]:
    frame = pd.read_csv(
        instrument_file, sep="\t", header=None,
        names=["asset", "valid_from", "valid_to"]
    )
    valid = frame.valid_from.le(last) & frame.valid_to.ge(first)
    symbols = sorted(frame.loc[valid, "asset"].unique())
    if not symbols:
        raise ValueError("No symbols for historical index membership interval")
    return symbols


def _exchange(symbol: str) -> str:
    return "sse" if symbol.startswith("SH") else "szse"


def fetch_eastmoney(session: requests.Session, symbol: str) -> tuple[list[dict], list[dict]]:
    code = symbol[2:]
    collected, requests_log = [], []
    first_total = None
    for page in range(1, 7):  # bounded cap; incomplete pages fail closed
        params = {
            "reportName": "RPT_SHAREBONUS_DET", "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageSize": 100, "pageNumber": page,
            "source": "WEB", "client": "WEB",
            "sortColumns": "EX_DIVIDEND_DATE", "sortTypes": "-1",
        }
        data, record = fetch_json(session, url=EM_URL, params=params)
        if not isinstance(data, dict) or data.get("success") is False:
            raise RuntimeError(f"Eastmoney reports error for {symbol}: {data.get('message') if isinstance(data,dict) else 'bad-json'}")
        body = data.get("result") or {}
        if first_total is None:
            first_total = int(body.get("count") or len(body.get("data") or []))
        values = body.get("data") or []
        requests_log.append(record)
        for row in values:
            if qlib_symbol(str(row.get("SECUCODE"))) != symbol:
                raise ValueError("Eastmoney 6-digit filtering returned unexpected exchange")
            collected.append(row)
        if len(collected) >= first_total:
            break
        if len(values) < 100:
            raise ValueError(f"Dividend pagination incomplete for {symbol}")
        time.sleep(0.28)
    if len(collected) < first_total:
        raise ValueError(f"Dividend page cap reached for {symbol}")
    return collected, requests_log


def fetch_cninfo(session: requests.Session, symbol: str,
                 first="2021-01-01", last="2022-12-31",
                 include_trading=False) -> tuple[list[dict], list[dict]]:
    code = symbol[2:]
    result, lookup = fetch_json(
        session, url=CN_ORG_URL,
        params={"keyWord": code, "maxNum": 10}, post=True,
    )
    matches = [r for r in result if r.get("code") == code]
    if len(matches) != 1:
        raise ValueError(f"Cannot resolve CNINFO orgId for {symbol}")
    org = matches[0]["orgId"]
    records, logs = [], [lookup]
    keys = ["分红派息", "权益分派"]
    if include_trading:
        keys += ["停牌", "复牌"]
    for keyword in keys:
        args = {
            "pageNum": "1", "pageSize": "100",
            "tabName": "fulltext", "column": _exchange(symbol),
            "stock": f"{code},{org}", "searchkey": keyword,
            "seDate": f"{first}~{last}", "isHLtitle": "true",
        }
        body, request = fetch_json(
            session, url=CN_NOTICE_URL, params=args, post=True,
        )
        if not isinstance(body, dict):
            raise ValueError("Expected CNINFO announcement JSON")
        if int(body.get("totalAnnouncement") or 0) > 100:
            raise ValueError(f"CNINFO pagination incomplete for {symbol}/{keyword}")
        records.extend(body.get("announcements") or [])
        logs.append(request)
        time.sleep(0.26)
    official = normalise_cninfo_announcements(records)
    # Same item may appear for multiple keywords; preserve unique IDs.
    unique = {r["announcement_id"]: r for r in official}
    return sorted(unique.values(),
                  key=lambda x: (x["published_calendar_date"], x["announcement_id"])), logs


def collect(
    *, symbols: list[str], output: Path,
    first_ex="2021-01-01", last_ex="2022-12-31",
    official_symbols: set[str] | None = None,
    pacing_seconds=0.42,
) -> dict:
    """Each symbol saved immediately for resume; no overwriting old snapshots."""
    if output.exists():
        raise FileExistsError(f"Evidence directory exists; cannot overwrite: {output}")
    output.mkdir(parents=True, exist_ok=False)
    official_symbols = official_symbols or set()
    records, failures = [], []
    with requests.Session() as session:
        for n, symbol in enumerate(symbols, 1):
            try:
                raw, meta = fetch_eastmoney(session, symbol)
                implemented, excluded = normalise_eastmoney_dividends(
                    raw, first_ex=first_ex, last_ex=last_ex,
                )
                official, official_meta = [], []
                if symbol in official_symbols:
                    official, official_meta = fetch_cninfo(
                        session, symbol, include_trading=(symbol == "SH600340"),
                    )
                events = attach_official_announcement(implemented, official)
                result = {
                    "symbol": symbol,
                    "real_data_not_synthetic": True,
                    "dividend_source": "Eastmoney public API; publication dates may be revised in later snapshots",
                    "official_index_source": "CNINFO original announcement metadata, where available",
                    "start_ex": first_ex, "end_ex": last_ex,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    "eastmoney_total_raw_records": len(raw),
                    "implemented_events_count": len(events),
                    "excluded": excluded,
                    "events": events, "official_announcements": official,
                    "requests_provenance": meta + official_meta,
                    "raw_eastmoney_records": raw,
                    "source_time_quality": (
                        "historical_calendar_dates_with_current_snapshot; "
                        "no publisher-time versioned feed across entire history"
                    ),
                }
                filepath = output/(symbol+".json")
                filepath.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8",
                )
                records.append({
                    "symbol": symbol, "impl_events": len(events),
                    "matched_official": sum(e["official_announcement_metadata_matches"]>0
                                            for e in events),
                    "official_announcements": len(official),
                    "origin_records": len(raw),
                    "local_evidence_json_sha256": sha_content(filepath.read_bytes()),
                })
                print(f"[{n}/{len(symbols)}] {symbol}: {len(events)} dated implementation events, "
                      f"{len(official)} official notice records", flush=True)
            except Exception as exc:
                item = {"symbol": symbol, "type": type(exc).__name__,
                        "message": str(exc)[:240]}
                failures.append(item)
                print(f"[{n}/{len(symbols)}] {symbol} FAILED: {item}", flush=True)
            time.sleep(pacing_seconds)
    overview = {
        "kind": "PARTIAL_OR_FULL_PIT_CORPORATE_ACTION_DATE_EVIDENCE",
        "requested": len(symbols), "complete_symbols": len(records),
        "failed_symbols": len(failures), "failures": failures,
        "implemented_events": sum(r["impl_events"] for r in records),
        "official_notice_crossmatched_events": sum(r["matched_official"] for r in records),
        "official_notice_records": sum(r["official_announcements"] for r in records),
        "study_ex_dates": [first_ex, last_ex],
        "publisher_intraday_timestamp_verified_for_all_events": False,
        "corporate_action_entitlements_audited_against_PDF_for_all_events": False,
        "listing_and_open_auction_execution_certified": False,
        "source_documents_and_records_in_gitignored_local_dir": True,
        "data_retrieval_mode": "PUBLIC_NO_CREDENTIALS_LOW_RATE",
        "symbols": records,
    }
    (output/"collection_summary.json").write_text(
        json.dumps(overview, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
    )
    return overview


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument("--index-file", type=Path)
    parser.add_argument("--official-symbols", nargs="*", default=[])
    parser.add_argument("--max-symbols", type=int, default=500)
    parser.add_argument("--delay", type=float, default=0.42)
    args = parser.parse_args()
    symbols = sorted({_symbol(x) for x in args.symbols})
    if args.index_file:
        symbols = sorted(set(symbols) | set(historical_csi300_union(args.index_file)))
    if not symbols or len(symbols) > args.max_symbols:
        raise ValueError("No securities selected or exceeded explicit max-symbols cap")
    if args.delay < 0.25:
        raise ValueError("Do not remove minimum per-symbol request pacing")
    official_symbols = {_symbol(x) for x in args.official_symbols}
    if not official_symbols.issubset(symbols):
        raise ValueError("Official lookup symbols must be among requested assets")
    summary = collect(
        symbols=symbols, output=args.output,
        official_symbols=official_symbols,
        pacing_seconds=args.delay,
    )
    print(json.dumps({
        key: summary[key] for key in (
            "requested", "complete_symbols", "failed_symbols",
            "implemented_events", "official_notice_crossmatched_events",
            "official_notice_records",
        )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
