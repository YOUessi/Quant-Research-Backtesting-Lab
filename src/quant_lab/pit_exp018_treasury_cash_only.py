"""EXP018: original issuer current cash-only, unchanged issued shares and treasury exclusion.

Only three full-SHA-pinned historical implementation PDFs qualify. Distinguish
pre-tax cash per *eligible* share from the diluted ex-price cash reference per
*total issued* share. Neither denotes actual broker credit or executable fills.
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal, ROUND_DOWN
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from pypdf import PdfReader

from .pit_original_date_recovery import issuer_implementation_dates
from .pit_official_batch import extract_explicit_pretax_cash_per_share
from .pit_share_distribution import clean, extract_share_terms

BASE_SHA256 = "fbe23fa6692f659c0e9990ce7aa27dabd156f818c4b91f4482e3a35fa3827eb4"
BASE_KIND = "EXP017_SUPPLEMENTAL_CURRENT_NO_SHARE_CAPITAL_CHANGE_CATALOG"
KIND = "EXP018_SUPPLEMENTAL_TREASURY_EXCLUDED_CASH_ONLY_CATALOG"
GRADE = "CURRENT_ISSUER_TREASURY_EXCLUDED_CASH_ONLY_NO_CAPITAL_CHANGE_EXP018"
PINNED = {
    ("SZ002311", "2021-07-09"): dict(
        event_id="c8379ad67a417cda1ae9fab3",
        sha256="10c5902cee6513ff6fafaf60f1cbd2f0d75627f3206186730c0b4f35294d280e",
        name="广东海大集团股份有限公司",
        title="2020年年度权益分派实施公告",
        issued=1661161061, treasury=10272108, eligible=1650888953,
        cash="0.32", total="528284464.96", ex_cash="0.3180212",
    ),
    ("SZ002311", "2022-07-07"): dict(
        event_id="55bcf5f18fa1fe8cac616eee",
        sha256="b235ff0808d2f271148baf55b9079d479da619bd66c3594608c1c194e72d02d0",
        name="广东海大集团股份有限公司",
        title="2021年年度权益分派实施公告",
        issued=1661161061, treasury=10272108, eligible=1650888953,
        cash="0.15", total="247633342.95", ex_cash="0.1490724",
    ),
    ("SZ300760", "2022-05-19"): dict(
        event_id="c4f06e528602dfb49bdd39e4",
        sha256="c1c1447f63bbc9d6d7cbc25a70ef80b83b33faa4734a34218aac1df2e1eb623a",
        name="深圳迈瑞生物医疗电子股份有限公司",
        title="2021年度权益分派实施公告",
        issued=1212441394, treasury=3048662, eligible=1209392732,
        cash="3.5", total="4232874562.00", ex_cash="3.4911993",
    ),
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

PLAN = re.compile(
    r"二、本次实施的权益分(?:派|配)方案(?P<plan>.*?)"
    r"三、股权登记日与除权除息日"
)
ELIGIBLE = re.compile(
    r"以公司现有总股本剔除已回购股份(?P<treasury>[\d,.]+)股后"
    r"的(?P<eligible>[\d,.]+)股为基数"
)
PER_TEN = re.compile(r"向全体股东每10股派(?P<cash>[\d.]+)元人民币现金（含税")
EX_REF = re.compile(
    r"(?P<total>[\d,]+\.\d+)÷(?P<issued>[\d,]+)(?:股)?="
    r"(?P<ref>\d+\.\d+)元/股"
)
UNCHANGED = (
    "实施权益分派前后公司总股本保持不变",
    "本次权益分派实施后，公司总股本保持不变",
)


def _number(value: str) -> int:
    d = Decimal(value.replace(",", ""))
    if d != d.to_integral_value() or d < 0:
        raise ValueError("Invalid source integral share count")
    return int(d)


def current_cash_only_treasury_proof(
    body: str, head: str, ticker: str, pin: dict,
) -> dict | None:
    """No inference from silence, adjustment boilerplate, or ex-price alone."""
    t, header = clean(body), clean(head)
    if (f"证券代码：{ticker[-6:]}" not in header or
            pin["name"] + pin["title"] not in header):
        return None
    intro_end = t.find("一、股东大会审议通过")
    sec6 = t.find("六、")
    if intro_end < 0 or sec6 <= intro_end:
        return None
    if not (any(claim in t[:intro_end] for claim in UNCHANGED)
            and any(claim in t[sec6:] for claim in UNCHANGED)):
        return None
    matches = list(PLAN.finditer(t))
    if len(matches) != 1:
        return None
    plan = matches[0].group("plan")
    if (any(word in plan for word in (
            "每10股送", "每10股转", "派送红股", "转增股本", "资本公积金转增",
            "同时送", "同时转增"))):
        return None
    m_eligible = list(ELIGIBLE.finditer(plan))
    m_cash = list(PER_TEN.finditer(plan))
    if len(m_eligible) != 1 or len(m_cash) != 1:
        return None
    try:
        treasury = _number(m_eligible[0].group("treasury"))
        eligible = _number(m_eligible[0].group("eligible"))
        cash = Decimal(m_cash[0].group("cash")) / Decimal(10)
    except Exception:
        return None
    if (treasury != pin["treasury"] or eligible != pin["eligible"]
            or cash != Decimal(pin["cash"]) or treasury == 0
            or treasury + eligible != pin["issued"]):
        return None
    # Total cash / *all* issued shares is the ex-price reference, not cash
    # claim per holder eligible share. The issuer truncates, not rounds, 7dp.
    refs = list(EX_REF.finditer(t))
    if not refs:
        return None
    total = Decimal(pin["total"])
    reference = Decimal(pin["ex_cash"])
    if (cash * eligible != total or
            (total / Decimal(pin["issued"])).quantize(
                Decimal("0.0000001"), rounding=ROUND_DOWN) != reference
            or reference >= cash):
        return None
    for m in refs:
        if (_number(m.group("issued")) != pin["issued"]
                or Decimal(m.group("total").replace(",", "")) != total
                or Decimal(m.group("ref")) != reference):
            return None
    return {
        "issuer_total_shares": pin["issued"],
        "treasury_shares_excluded_from_distribution": treasury,
        "issuer_cash_eligible_shares": eligible,
        "gross_cash_per_cash_eligible_share": str(cash),
        "issuer_total_gross_cash_scheduled": str(total),
        "ex_price_reference_cash_per_issued_share": str(reference),
        "cash_reference_not_holder_cash_claim": True,
        "current_issuer_no_new_shares": True,
    }


def verify_source(row: dict, pdf: bytes) -> dict:
    key = row.get("symbol"), row.get("ex_date")
    pin = PINNED.get(key)
    if pin is None:
        raise ValueError("Unreviewed original issuer event")
    sha = hashlib.sha256(pdf).hexdigest()
    if (sha != pin["sha256"] or row.get("issuer_original_pdf_sha256") != sha
            or row.get("event_id") != pin["event_id"]
            or not pdf.startswith(b"%PDF")):
        raise ValueError("Wrong complete original PDF SHA256 or issuer identity")
    notice = row.get("announcement_day")
    url = row.get("issuer_original_pdf_url")
    if (not isinstance(notice, str) or not isinstance(url, str)
            or not re.fullmatch(
                r"https://static\.cninfo\.com\.cn/finalpage/"
                + re.escape(notice) + r"/\d+\.PDF", url)):
        raise ValueError("Original issuer publication path/day not certified")
    reader = PdfReader(BytesIO(pdf), strict=False)
    if not reader.pages:
        raise ValueError("Empty original PDF")
    first = reader.pages[0].extract_text() or ""
    body = "\n".join(page.extract_text() or "" for page in reader.pages[:5])
    proof = current_cash_only_treasury_proof(body, first, row["symbol"], pin)
    if proof is None:
        raise ValueError("Current issuer cash-only and capital proof not established")
    terms = extract_share_terms(body)
    if (terms["bonus_per_ten_distinct_candidates"]
            or terms["transfer_per_ten_distinct_candidates"]
            or terms["bonus_source_status"].startswith("CONFLICTING")
            or terms["transfer_source_status"].startswith("CONFLICTING")):
        raise ValueError("Positive or conflicting current share rights")
    dates = issuer_implementation_dates(body, row["symbol"])
    if (dates["status"] != "PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED"
            or dates["record_date"] != row["record_date"]
            or dates["ex_date"] != row["ex_date"]
            or dates["pay_date"] != row["scheduled_cash_payment_day"]):
        raise ValueError("Issuer record/ex/scheduled cash date mismatch")
    cash = extract_explicit_pretax_cash_per_share(body)
    if (len(cash) != 1 or Decimal(str(cash[0])) != Decimal(pin["cash"])
            or Decimal(str(row["gross_cash_per_old_nominal_share"]))
               != Decimal(pin["cash"])):
        raise ValueError("Original holder-eligible cash ratio mismatch")
    if not (notice < row["earliest_usable_exchange_day"]
            <= row["record_date"] < row["ex_date"]):
        raise ValueError("Issuer publication not embargoed before eligibility")
    if (row["complete_rights_supported_by_issuer_original"]
            or row["bonus_shares_per_old_share"] is not None
            or row["capital_transfer_shares_per_old_share"] is not None
            or row["full_new_nominal_share_multiplier"] is not None):
        raise ValueError("New evidence cannot overwrite known share rights")
    for flag in ("broker_share_delivery_and_cash_payment_verified",
                 "historical_factor_vintage_available",
                 "original_publication_intraday_time_certified"):
        if row.get(flag) is not False:
            raise ValueError("Unsupported broker, factor, or intraday source flag")
    return {
        "event_id": pin["event_id"], "symbol": key[0], "ex_date": key[1],
        "source_full_sha256": sha, "original_url": url,
        "notice_day": notice,
        "conservative_next_session": row["earliest_usable_exchange_day"],
        "record_date": dates["record_date"],
        "scheduled_pay_date_not_broker_credit": dates["pay_date"],
        "gross_cash_claim_per_eligible_share": str(Decimal(pin["cash"])),
        "source_grade": GRADE, **proof,
        "actual_broker_cash_or_stock_credit_verified": False,
        "real_order_fills_or_limit_prices_verified": False,
    }


def apply_proof(row: dict, proof: dict) -> dict:
    key = row.get("symbol"), row.get("ex_date")
    pin = PINNED.get(key)
    if (pin is None or row.get("event_id") != pin["event_id"]
            or proof.get("event_id") != pin["event_id"]
            or row.get("issuer_original_pdf_sha256") != pin["sha256"]
            or proof.get("source_full_sha256") != pin["sha256"]
            or proof.get("source_grade") != GRADE
            or proof.get("current_issuer_no_new_shares") is not True
            or proof.get("issuer_total_shares") != pin["issued"]
            or proof.get("treasury_shares_excluded_from_distribution") != pin["treasury"]
            or proof.get("issuer_cash_eligible_shares") != pin["eligible"]
            or proof.get("cash_reference_not_holder_cash_claim") is not True
            or proof.get("actual_broker_cash_or_stock_credit_verified") is not False
            or Decimal(str(proof.get("gross_cash_per_cash_eligible_share", "-1")))
               != Decimal(pin["cash"])
            or Decimal(str(proof.get("ex_price_reference_cash_per_issued_share", "-1")))
               != Decimal(pin["ex_cash"])
            or row["complete_rights_supported_by_issuer_original"]
            or row["bonus_shares_per_old_share"] is not None
            or row["capital_transfer_shares_per_old_share"] is not None
            or row["full_new_nominal_share_multiplier"] is not None):
        raise ValueError("Unverified issuer proof or existing rights may not be overwritten")
    before = copy.deepcopy(row)
    after = copy.deepcopy(row)
    after["exp018_previous_rights_evidence"] = copy.deepcopy(row["rights_evidence"])
    after["bonus_shares_per_old_share"] = 0.0
    after["capital_transfer_shares_per_old_share"] = 0.0
    after["full_new_nominal_share_multiplier"] = 1.0
    after["complete_rights_supported_by_issuer_original"] = True
    after["rights_evidence"] = {"bonus": GRADE, "transfer": GRADE}
    after["exp018_original_issuer_treasury_cash_proof"] = copy.deepcopy(proof)
    for field in FROZEN_FIELDS:
        if before[field] != after[field]:
            raise AssertionError("Immutable original date/cash/credit/source changed")
    return after


def run(parent: Path, pdf_dirs: list[Path], out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Prior experiment outputs must not be overwritten")
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError("Wrong full-byte frozen EXP017 input catalog SHA256")
    old = json.loads(raw)
    if (old.get("kind") != BASE_KIND
            or (old.get("issuer_events"),
                old.get("fully_verified_nominal_share_rights"),
                old.get("unknown_share_rights")) != (89, 40, 49)):
        raise ValueError("Unexpected frozen source catalog version")
    rows = old["events"]
    by_key = {(r["symbol"], r["ex_date"]): r for r in rows}
    if len(rows) != 89 or len(by_key) != 89 or not set(PINNED) <= set(by_key):
        raise ValueError("Duplicate or missing original issuer event")
    source_map: dict[str, Path] = {}
    for folder in pdf_dirs:
        if not folder.is_dir():
            raise FileNotFoundError("Missing original local issuer archive: " + str(folder))
        for p in folder.glob("*.pdf"):
            source_map[hashlib.sha256(p.read_bytes()).hexdigest()] = p
    for row in rows:
        sha = row.get("issuer_original_pdf_sha256")
        if not isinstance(sha, str) or not re.fullmatch("[0-9a-f]{64}", sha):
            raise ValueError("Missing issuer full original SHA256")
        p = source_map.get(sha)
        if p is None or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError("Missing/modified original issuer PDF for " + row["event_id"])
    proofs = {key: verify_source(by_key[key], source_map[pin["sha256"]].read_bytes())
              for key, pin in PINNED.items()}
    derived = copy.deepcopy(old)
    derived["kind"] = KIND
    derived["source_exp017_catalog_full_sha256"] = BASE_SHA256
    derived["events"] = [
        apply_proof(r, proofs[r["symbol"], r["ex_date"]])
        if (r["symbol"], r["ex_date"]) in proofs else copy.deepcopy(r)
        for r in rows
    ]
    derived["fully_verified_nominal_share_rights"] = sum(
        bool(r["complete_rights_supported_by_issuer_original"])
        for r in derived["events"])
    derived["unknown_share_rights"] = 89 - derived["fully_verified_nominal_share_rights"]
    derived["exp018_current_treasury_excluded_cash_only_proofs"] = 3
    if (derived["fully_verified_nominal_share_rights"],
            derived["unknown_share_rights"]) != (43, 46):
        raise AssertionError("Exact issuer evidence coverage changed")
    newbytes = (json.dumps(derived, ensure_ascii=False, indent=2) + "\n").encode()
    audit = {
        "kind": "EXP018_THREE_ORIGINAL_ISSUER_TREASURY_EXCLUDED_CASH_ONLY_PROOFS",
        "input_frozen_exp017_catalog_sha256": BASE_SHA256,
        "derived_exp018_catalog_sha256": hashlib.sha256(newbytes).hexdigest(),
        "original_issuer_pdf_full_sha256_checked": 89,
        "new_current_issuer_source_proofs": 3,
        "previous_unknown_to_zero_fields": 6,
        "old_complete_unknown": [40, 49], "new_complete_unknown": [43, 46],
        "other_events_json_equal": 86,
        "no_prior_pdf_or_catalog_overwrite": True,
        "broker_credit_or_execution_certified": False,
        "published_vintage_factors_certified": False,
        "official_exchange_limit_price_certified": False,
        "prior_frozen_returns_modified": False,
        "primary_evidence": [proofs[k] for k in sorted(proofs)],
    }
    out.mkdir(parents=True)
    (out / "rights_catalog_exp018.json").write_bytes(newbytes)
    (out / "source_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-catalog", type=Path, required=True)
    p.add_argument("--issuer-pdfs", type=Path, nargs="+", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args.parent_catalog, args.issuer_pdfs, args.out_dir),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
