"""EXP017: directly stated *current distribution* with no issued share-capital change.

Two hash-pinned issuer originals, not adjusted market data, prove a cash-only
current implementation. Never infer zero shares from mere absence of language
or '差异化分红送转：否'. Brokerage posting and sellability remain unverified.
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

BASE_SHA256 = "60a3187bff82f4d4a0eae82b3cbb83afc0749593a1ebcd817e17145cb7eb2d9d"
BASE_KIND = "EXP016_SUPPLEMENTAL_EXPLICIT_NO_STOCK_ISSUER_RIGHTS_CATALOG"
GRADE = "CURRENT_ISSUER_IMPLEMENTATION_DIRECT_NO_SHARE_CAPITAL_CHANGE_EXP017"
NAME = "云南沃森生物技术股份有限公司"
CLAIM = "本次权益分派不会导致公司总股本发生变动"
CAPITAL_SECTION = re.compile(
    r"五、公司总股本变动情况"
    r"分红前公司总股本为(?P<before>[\d,]+)股，"
    r"分红后总股本为(?P<after>[\d,]+)股。"
    + re.escape(CLAIM) + r"。六、调整相关参数"
)
PINNED = {
    ("SZ300142", "2021-05-19"): {
        "event_id": "5649684883755b881034232b",
        "sha256": "d286a7ac7a16d4cd09d477d5df7e8d00ee9d766e509dafb7806997c10667af22",
        "fiscal": "2020", "share_capital": 1566186984,
    },
    ("SZ300142", "2022-04-26"): {
        "event_id": "c88ee5378b8bc5f72afc4147",
        "sha256": "8589fb592fa05c8c3ac4a23c663661bc0a99541d33642eac4a95eb2007b1daa6",
        "fiscal": "2021", "share_capital": 1601571884,
    },
}
FROZEN_FIELDS = (
    "event_id", "symbol", "announcement_day", "earliest_usable_exchange_day",
    "record_date", "ex_date", "scheduled_cash_payment_day",
    "gross_cash_per_old_nominal_share", "issuer_original_pdf_sha256",
    "issuer_original_pdf_url", "cash_rights_nominal_not_qlib_adjusted",
    "broker_share_delivery_and_cash_payment_verified",
    "historical_factor_vintage_available",
    "original_publication_intraday_time_certified",
)


def current_no_capital_change(text: str, first_page: str, fiscal: str,
                              expected_total: int) -> bool:
    """Require exact current issuer/title, cash-only plan AND current capital section."""
    t, head = clean(text), clean(first_page)
    if (f"证券代码：300142" not in head or
            f"{NAME}{fiscal}年年度权益分派实施公告" not in head):
        return False
    if (t.count(CLAIM) != 1 or
            t.count("五、公司总股本变动情况") != 1):
        return False
    matches = list(CAPITAL_SECTION.finditer(t))
    if len(matches) != 1:
        return False
    m = matches[0]
    before = int(m.group("before").replace(",", ""))
    after = int(m.group("after").replace(",", ""))
    if before != after or before != expected_total or before <= 0:
        return False
    # Boilerplate in option-price 'adjustment parameters' is NOT a current transfer.
    # Restrict actual distribution plan to explicitly cash-only text.
    start = t.find("4、权益分派方案")
    end = t.find("二、股权登记日与除权除息日")
    if not (0 <= start < end < m.start()):
        return False
    plan = t[start:end]
    if "向全体股东每10股派" not in plan:
        return False
    if (re.search(r"(每10股|每股).{0,12}(送红股|送股|转增)", plan)
            or "同时，以资本公积金" in plan):
        return False
    method = t.find("四、权益分派方法")
    if not (end < method < m.start() and
            "现金红利" in t[method:m.start()]):
        return False
    return True


def verify_source(event: dict, pdf: bytes) -> dict:
    key = (event.get("symbol"), event.get("ex_date"))
    pin = PINNED.get(key)
    if pin is None:
        raise ValueError("Unreviewed source identity")
    sha = hashlib.sha256(pdf).hexdigest()
    if (sha != pin["sha256"] or
            event.get("issuer_original_pdf_sha256") != sha or
            event.get("event_id") != pin["event_id"]):
        raise ValueError("Original PDF full SHA256 or event identity mismatch")
    if not pdf.startswith(b"%PDF"):
        raise ValueError("Not a source PDF")
    notice = event.get("announcement_day")
    url = event.get("issuer_original_pdf_url")
    if (not isinstance(notice, str) or not isinstance(url, str) or
            not re.fullmatch(r"https://static\.cninfo\.com\.cn/finalpage/" +
                             re.escape(notice) + r"/\d+\.PDF", url)):
        raise ValueError("Wrong original announcement URL or release-day identity")
    reader = PdfReader(BytesIO(pdf), strict=False)
    if not reader.pages:
        raise ValueError("Original announcement has no pages")
    head = reader.pages[0].extract_text() or ""
    body = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
    if not current_no_capital_change(body, head, pin["fiscal"],
                                     pin["share_capital"]):
        raise ValueError("Current issuer explicit no-capital-change source not proven")
    terms = extract_share_terms(body)
    if (terms["bonus_per_ten_distinct_candidates"] or
            terms["transfer_per_ten_distinct_candidates"] or
            terms["bonus_source_status"].startswith("CONFLICTING") or
            terms["transfer_source_status"].startswith("CONFLICTING")):
        raise ValueError("Positive/contradictory bonus or transfer rights")
    dates = issuer_implementation_dates(body, event["symbol"])
    if (dates["status"] != "PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED" or
            dates["record_date"] != event["record_date"] or
            dates["ex_date"] != event["ex_date"] or
            dates["pay_date"] != event["scheduled_cash_payment_day"]):
        raise ValueError("Original issuer record/ex/payment dates conflict")
    cash = extract_explicit_pretax_cash_per_share(body)
    if (len(cash) != 1 or
            Decimal(str(cash[0])) !=
            Decimal(str(event["gross_cash_per_old_nominal_share"]))):
        raise ValueError("Original pre-tax cash declaration conflicts")
    if not (notice < event["earliest_usable_exchange_day"]
            <= event["record_date"] < event["ex_date"]):
        raise ValueError("Issuer announcement embargo or ex-date invalid")
    if (event["complete_rights_supported_by_issuer_original"] or
            event["bonus_shares_per_old_share"] is not None or
            event["capital_transfer_shares_per_old_share"] is not None or
            event["full_new_nominal_share_multiplier"] is not None):
        raise ValueError("Rights are not both unknown")
    for flag in ("original_publication_intraday_time_certified",
                 "historical_factor_vintage_available",
                 "broker_share_delivery_and_cash_payment_verified"):
        if event.get(flag) is not False:
            raise ValueError("Unsupported evidence grade/third-party credit flag")
    return {
        "event_id": pin["event_id"], "symbol": key[0], "ex_date": key[1],
        "source_full_sha256": sha, "original_url": url,
        "original_notice_day": notice,
        "first_next_exchange_session": event["earliest_usable_exchange_day"],
        "record_day": dates["record_date"], "ex_day": dates["ex_date"],
        "scheduled_cash_pay_day_not_broker_credit": dates["pay_date"],
        "pre_tax_cash_per_old_nominal_share": str(cash[0]),
        "fiscal_year_in_original_title": pin["fiscal"],
        "issuer_declared_before_and_after_total": pin["share_capital"],
        "issuer_exact_current_capital_claim": CLAIM,
        "source_grade": GRADE,
        "issuer_current_plan_no_stock_issuance": True,
        "intraday_publication_or_broker_credit_proven": False,
        "actual_sellable_shares_or_trade_executions_proven": False,
    }


def apply_proof(row: dict, proof: dict) -> dict:
    key = (row.get("symbol"), row.get("ex_date"))
    pin = PINNED.get(key)
    if (pin is None or pin["event_id"] != row.get("event_id") or
            pin["event_id"] != proof.get("event_id") or
            pin["sha256"] != row.get("issuer_original_pdf_sha256") or
            pin["sha256"] != proof.get("source_full_sha256") or
            proof.get("source_grade") != GRADE or
            proof.get("issuer_current_plan_no_stock_issuance") is not True or
            proof.get("issuer_declared_before_and_after_total") != pin["share_capital"] or
            row["complete_rights_supported_by_issuer_original"] or
            row["bonus_shares_per_old_share"] is not None or
            row["capital_transfer_shares_per_old_share"] is not None or
            row["full_new_nominal_share_multiplier"] is not None):
        raise ValueError("Proof was not verified for two unknown stock categories")
    before = copy.deepcopy(row)
    after = copy.deepcopy(row)
    after["exp017_previous_rights_evidence"] = copy.deepcopy(row["rights_evidence"])
    after["bonus_shares_per_old_share"] = 0.0
    after["capital_transfer_shares_per_old_share"] = 0.0
    after["full_new_nominal_share_multiplier"] = 1.0
    after["complete_rights_supported_by_issuer_original"] = True
    after["rights_evidence"] = {"bonus": GRADE, "transfer": GRADE}
    after["exp017_original_issuer_proof"] = copy.deepcopy(proof)
    for field in FROZEN_FIELDS:
        if after[field] != before[field]:
            raise AssertionError("Historical source/cash/timing field mutated")
    return after


def run(parent_catalog: Path, pdf_dirs: list[Path], out_dir: Path) -> dict:
    if out_dir.exists():
        raise FileExistsError("Existing audit outputs are immutable")
    payload = parent_catalog.read_bytes()
    if hashlib.sha256(payload).hexdigest() != BASE_SHA256:
        raise ValueError("Frozen EXP016 full-byte catalog SHA256 mismatch")
    original = json.loads(payload)
    if (original.get("kind") != BASE_KIND or
            (original.get("issuer_events"),
             original.get("fully_verified_nominal_share_rights"),
             original.get("unknown_share_rights")) != (89, 38, 51)):
        raise ValueError("Invalid frozen EXP016 event count/identity")
    rows = original["events"]
    old = {(r["symbol"], r["ex_date"]): r for r in rows}
    if len(rows) != 89 or len(old) != 89 or not set(PINNED) <= set(old):
        raise ValueError("Duplicate or missing issuer events")
    source_map = {}
    for folder in pdf_dirs:
        if not folder.is_dir():
            raise FileNotFoundError("Missing local immutable PDF archive: " + str(folder))
        for pdf in folder.glob("*.pdf"):
            source_map[hashlib.sha256(pdf.read_bytes()).hexdigest()] = pdf
    for row in rows:
        sha = row.get("issuer_original_pdf_sha256")
        if not isinstance(sha, str) or not re.fullmatch("[a-f0-9]{64}", sha):
            raise ValueError("Invalid source PDF SHA256 field")
        if sha not in source_map:
            raise FileNotFoundError("Missing authenticated issuer PDF: " + row["event_id"])
        if hashlib.sha256(source_map[sha].read_bytes()).hexdigest() != sha:
            raise ValueError("Issuer source PDF modified during verification")
    proofs = {key: verify_source(old[key],
                              source_map[pin["sha256"]].read_bytes())
              for key, pin in PINNED.items()}
    derived = copy.deepcopy(original)
    derived["kind"] = "EXP017_SUPPLEMENTAL_CURRENT_NO_SHARE_CAPITAL_CHANGE_CATALOG"
    derived["source_exp016_catalog_full_sha256"] = BASE_SHA256
    derived["events"] = [
        apply_proof(row, proofs[(row["symbol"], row["ex_date"])])
        if (row["symbol"], row["ex_date"]) in proofs else copy.deepcopy(row)
        for row in rows
    ]
    derived["fully_verified_nominal_share_rights"] = sum(
        r["complete_rights_supported_by_issuer_original"] for r in derived["events"]
    )
    derived["unknown_share_rights"] = 89 - derived["fully_verified_nominal_share_rights"]
    derived["exp017_direct_current_issuer_no_new_stock_proofs"] = 2
    if (derived["fully_verified_nominal_share_rights"],
            derived["unknown_share_rights"]) != (40, 49):
        raise AssertionError("Source coverage changed unexpectedly")
    output_bytes = (json.dumps(derived, ensure_ascii=False, indent=2) + "\n").encode()
    audit = {
        "kind": "EXP017_TWO_CURRENT_ISSUER_NO_SHARE_CAPITAL_CHANGE_PROOFS",
        "frozen_exp016_catalog_sha256": BASE_SHA256,
        "new_exp017_catalog_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "archived_source_pdf_complete_sha256s_rechecked": 89,
        "current_issuer_original_direct_proofs": 2,
        "newly_filled_zero_categories": 4,
        "old_complete_unknown": [38, 51],
        "new_complete_unknown": [40, 49],
        "other_original_event_rows_unchanged": 87,
        "original_pdfs_or_frozen_catalog_modified": False,
        "official_daily_limit_and_broker_order_fill_certified": False,
        "intraday_release_timestamps_certified": False,
        "actual_cash_or_new_stock_broker_credit_certified": False,
        "historical_asof_adjustment_factors_certified": False,
        "new_backtest_or_independent_returns_claimed": False,
        "primary_evidence": [proofs[k] for k in sorted(proofs)],
    }
    out_dir.mkdir(parents=True)
    (out_dir / "rights_catalog_exp017.json").write_bytes(output_bytes)
    (out_dir / "source_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-catalog", type=Path, required=True)
    p.add_argument("--issuer-pdfs", nargs="+", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.parent_catalog, a.issuer_pdfs, a.out_dir),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
