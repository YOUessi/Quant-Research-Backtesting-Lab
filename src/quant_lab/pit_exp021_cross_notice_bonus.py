"""EXP021: pin a second pre-ex-date issuer source to resolve one missing bonus field.

The issuer's 2021-Q1 report explicitly said no bonus, 8-for-10 capital
transfer. A later original implementation filing confirms the approved plan
was unchanged, while disclosing a 1,500-share option exercise. Neither report
can certify actual shareholder account postings, executions or factor vintages.
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

from .pit_share_distribution import clean
from .pit_exp019_unresolved_rights_negative import source_inventory

BASE_SHA256 = "62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122"
BASE_KIND = "EXP018_SUPPLEMENTAL_TREASURY_EXCLUDED_CASH_ONLY_CATALOG"
RESULT_KIND = "EXP021_CROSS_ISSUER_NOTICES_RESOLVED_BONUS_CATALOG"
AUDIT_KIND = "EXP021_PRIOR_ISSUER_PLAN_AND_FINAL_IMPLEMENTATION_RIGHTS_AUDIT"
GRADE = "TWO_PRE_EX_DATE_ORIGINAL_ISSUER_SOURCES_MATCH_IMPLEMENTATION_EXP021"
SYMBOL = "SZ300751"
EX_DATE = "2021-05-18"
EVENT_ID = "4172b0cd291fcc8ead62d3fa"
IMPLEMENTATION_SHA = "85d4cd86d50e4740767ed517454a7a1db69994ac5b6837e74ae11b3d7cf4984d"
IMPLEMENTATION_URL = "https://static.cninfo.com.cn/finalpage/2021-05-10/1209949702.PDF"
QUARTERLY_SHA = "7875834e9055ac8914d9db533f1aa811fefeb6244c18f5c8ddfd315d3509e68f"
QUARTERLY_URL = ("https://disc.static.szse.cn/download/disc/disk02/finalpage/"
                 "2021-04-28/f26e0b8e-fed8-42cb-92dc-5567c9d13ffa.PDF")
QUARTERLY_DATE = "2021-04-28"
FROZEN_FIELDS = (
    "event_id", "symbol", "announcement_day", "earliest_usable_exchange_day",
    "record_date", "ex_date", "scheduled_cash_payment_day",
    "gross_cash_per_old_nominal_share", "issuer_original_pdf_sha256",
    "issuer_original_pdf_url", "cash_rights_nominal_not_qlib_adjusted",
    "broker_share_delivery_and_cash_payment_verified",
    "historical_factor_vintage_available",
    "original_publication_intraday_time_certified",
)


def _text(pdf: bytes, sha: str, *, first_pages: int = 30) -> tuple[str, str]:
    if not pdf.startswith(b"%PDF") or hashlib.sha256(pdf).hexdigest() != sha:
        raise ValueError("Original issuer PDF complete SHA256/content mismatch")
    reader = PdfReader(BytesIO(pdf), strict=False)
    if not reader.pages:
        raise ValueError("Empty original issuer PDF")
    first = reader.pages[0].extract_text() or ""
    body = "".join(p.extract_text() or "" for p in reader.pages[:first_pages])
    return clean(first), clean(body)


def check_plan_link(quarterly_first: str, quarterly_text: str,
                    implementation_first: str, implementation_text: str) -> dict:
    """Review only a specifically identified proposal + its approved implementation.

    No absence-of-stock-text proof: the earlier original must literally say
    不送红股. The later original must identify that proposal/approval and
    affirm the implemented plan is the same, including all quantitative terms.
    """
    if not ("苏州迈为科技股份有限公司2021年第一季度报告" in quarterly_first
            and "2021-041" in quarterly_first):
        raise ValueError("Wrong first-page issuer quarterly report")
    if not ("证券代码：300751" in implementation_first
            and "苏州迈为科技股份有限公司2020年年度权益分派实施公告"
            in implementation_first):
        raise ValueError("Wrong final implementation issuer/ticker/period")
    qstart = quarterly_text.find("2020年度利润分配事项")
    qend = quarterly_text.find("重要事项概述", qstart)
    if not (0 <= qstart < qend):
        raise ValueError("Missing scoped pre-approval issuer plan")
    proposal = quarterly_text[qstart:qend]
    expected_q = (
        "2021年4月9日召开第二届董事会第十三次会议",
        "57,277,225股为基数",
        "每10股派发现金红利15元（含税）",
        "不送红股；同时以资本公积金向全体股东每10股转增8股",
        "合计转增45,821,780股",
        "转增后公司总股本为103,099,005股",
        "尚需经过2020年年度股东大会审议通过",
    )
    if not all(value in proposal for value in expected_q):
        raise ValueError("Prior issuer proposal/explicit zero bonus is missing or inconsistent")
    a = implementation_text.find("一、股东大会审议通过利润分配及资本公积金转增股本方案的情况")
    b = implementation_text.find("二、本次实施的利润分配及资本公积金转增股本方案")
    c = implementation_text.find("三、权益分派日期", b)
    if not (0 <= a < b < c):
        raise ValueError("Current implementation section boundaries missing")
    approval = implementation_text[a:b]
    current = implementation_text[b:c]
    required_approval = (
        "2021年4月30日",
        "2021年4月10日", "2021-030",
        "股本由57,277,225股增加至57,278,725股",
        "送红股比例、资本公积金转增股本比例固定不变",
        "每10股派发现金红利15元（含税）不变",
        "每10股转增8股不变",
        "本次实施的分配方案与股东大会审议通过的分配方案一致",
    )
    if not all(value in approval for value in required_approval):
        raise ValueError("Issuer meeting/approved-plan continuity not proven")
    required_current = (
        "以公司现有总股本57,278,725股为基数",
        "每10股派15.000000元人民币现金",
        "以资本公积金向全体股东每10股转增8股",
        "分红前本公司总股本为57,278,725股",
        "分红后总股本增至103,101,705股",
    )
    if not all(value in current for value in required_current):
        raise ValueError("Current implemented cash/transfer/share totals conflict")
    if (Decimal("57277225") * Decimal(".8") != Decimal("45821780") or
            Decimal("57278725") * Decimal(".8") != Decimal("45822980") or
            57278725 + 45822980 != 103101705):
        raise ValueError("Source expected issued-share arithmetic invalid")
    return {
        "prior_fiscal_plan_no_bonus_explicit": True,
        "prior_plan_cash_per_old_share_cny": "1.5",
        "plan_transfer_per_old_share": "0.8",
        "preapproval_shares": 57277225,
        "implementation_shares_before": 57278725,
        "intervening_exercise_share_increase": 1500,
        "current_transfer_shares": 45822980,
        "implementation_shares_after": 103101705,
        "bonus_per_old_share": "0",
        "nominal_multiplier": "1.8",
    }


def verify_two_sources(row: dict, quarterly_pdf: bytes, current_pdf: bytes) -> dict:
    if ((row.get("symbol"), row.get("ex_date"), row.get("event_id"))
            != (SYMBOL, EX_DATE, EVENT_ID)
            or row.get("issuer_original_pdf_sha256") != IMPLEMENTATION_SHA
            or row.get("issuer_original_pdf_url") != IMPLEMENTATION_URL):
        raise ValueError("Unapproved current issuer original/event identity")
    if not (row["announcement_day"] == "2021-05-10" and
            row["earliest_usable_exchange_day"] == "2021-05-11" and
            row["record_date"] == "2021-05-17" and
            row["ex_date"] == EX_DATE and
            row["scheduled_cash_payment_day"] is None):
        raise ValueError("Final implementation publication/record/ex clock mismatch")
    if not (QUARTERLY_DATE < row["announcement_day"] <
            row["record_date"] < row["ex_date"]):
        raise ValueError("Earlier original report was not contemporaneous")
    if (row["complete_rights_supported_by_issuer_original"] is not False
            or row["bonus_shares_per_old_share"] is not None
            or Decimal(str(row["capital_transfer_shares_per_old_share"])) != Decimal(".8")
            or row["full_new_nominal_share_multiplier"] is not None
            or Decimal(str(row["gross_cash_per_old_nominal_share"])) != Decimal("1.5")
            or row["rights_evidence"].get("bonus") != "BONUS_UNCONFIRMED"):
        raise ValueError("Pre-existing rights/issuer cash conflict")
    if not (row["broker_share_delivery_and_cash_payment_verified"] is False
            and row["historical_factor_vintage_available"] is False
            and row["original_publication_intraday_time_certified"] is False):
        raise ValueError("Unverified broker/source-vintage flags promoted")
    q_first,q_text=_text(quarterly_pdf,QUARTERLY_SHA)
    i_first,i_text=_text(current_pdf,IMPLEMENTATION_SHA,first_pages=6)
    terms=check_plan_link(q_first,q_text,i_first,i_text)
    return {
        "event_id": EVENT_ID, "symbol": SYMBOL, "ex_date": EX_DATE,
        "quarterly_source_pdf_url": QUARTERLY_URL,
        "quarterly_source_pdf_full_sha256": QUARTERLY_SHA,
        "quarterly_publication_day": QUARTERLY_DATE,
        "quarterly_conservative_first_usable_day": "2021-04-29",
        "final_implementation_pdf_url": IMPLEMENTATION_URL,
        "final_implementation_pdf_full_sha256": IMPLEMENTATION_SHA,
        "final_implementation_notice_day": "2021-05-10",
        "final_implementation_first_usable_day": row["earliest_usable_exchange_day"],
        "source_grade": GRADE,
        **terms,
        "actual_holder_share_rounding_or_delivery_confirmed": False,
        "actual_broker_cash_receipt_confirmed": False,
        "as_published_price_adjustment_factor_confirmed": False,
        "actual_exchange_auction_fill_or_sellable_shares_confirmed": False,
        "subsequent_amendment_exhaustiveness_confirmed": False,
    }


def apply_proof(row: dict, proof: dict) -> dict:
    if (row.get("event_id") != EVENT_ID or
            proof.get("source_grade") != GRADE or
            proof.get("event_id") != EVENT_ID or
            proof.get("quarterly_source_pdf_full_sha256") != QUARTERLY_SHA or
            proof.get("final_implementation_pdf_full_sha256") != IMPLEMENTATION_SHA or
            proof.get("prior_fiscal_plan_no_bonus_explicit") is not True or
            proof.get("bonus_per_old_share") != "0" or
            proof.get("nominal_multiplier") != "1.8" or
            proof.get("implementation_shares_before") != 57278725 or
            proof.get("implementation_shares_after") != 103101705 or
            row.get("bonus_shares_per_old_share") is not None or
            Decimal(str(row.get("capital_transfer_shares_per_old_share"))) != Decimal(".8") or
            row.get("complete_rights_supported_by_issuer_original") is not False):
        raise ValueError("Unapproved or forged original issuer proof")
    original=copy.deepcopy(row)
    updated=copy.deepcopy(row)
    updated["exp021_previous_rights_evidence"]=copy.deepcopy(row["rights_evidence"])
    updated["bonus_shares_per_old_share"]=0.0
    updated["full_new_nominal_share_multiplier"]=1.8
    updated["complete_rights_supported_by_issuer_original"]=True
    updated["rights_evidence"]["bonus"]=GRADE
    updated["exp021_cross_issuer_original_notice_proof"]=copy.deepcopy(proof)
    if any(updated[k]!=original[k] for k in FROZEN_FIELDS):
        raise AssertionError("Old cash, source, date, payment flags modified")
    if updated["capital_transfer_shares_per_old_share"] != original["capital_transfer_shares_per_old_share"]:
        raise AssertionError("Already proven capitalization ratio overwritten")
    return updated


def run(parent_catalog: Path, archive_dirs: list[Path],
        quarterly_pdf: Path, out_dir: Path) -> dict:
    if out_dir.exists():
        raise FileExistsError("Never overwrite prior evidence or originals")
    raw=parent_catalog.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA256:
        raise ValueError("Frozen source catalog complete SHA256 mismatch")
    base=json.loads(raw)
    rows=base["events"]
    if (base.get("kind")!=BASE_KIND or len(rows)!=89 or
            base["issuer_events"]!=89 or
            (base["fully_verified_nominal_share_rights"],base["unknown_share_rights"])!=(43,46) or
            len({(r["symbol"],r["ex_date"]) for r in rows})!=89):
        raise ValueError("Wrong immutable event coverage")
    bykey={(r["symbol"],r["ex_date"]):r for r in rows}
    src,checked=source_inventory(rows,archive_dirs)  # all 89 full PDF hashes and headers
    qraw=quarterly_pdf.read_bytes()
    original=bykey[(SYMBOL,EX_DATE)]
    proof=verify_two_sources(original,qraw,src[IMPLEMENTATION_SHA].read_bytes())
    out=copy.deepcopy(base)
    out["kind"]=RESULT_KIND
    out["source_exp018_catalog_full_sha256"]=BASE_SHA256
    out["events"]=[apply_proof(row,proof) if row["event_id"]==EVENT_ID
                   else copy.deepcopy(row) for row in rows]
    out["fully_verified_nominal_share_rights"]=sum(
        bool(r["complete_rights_supported_by_issuer_original"]) for r in out["events"])
    out["unknown_share_rights"]=89-out["fully_verified_nominal_share_rights"]
    out["exp021_newly_verified_zero_bonus_events"]=1
    out["exp021_added_secondary_original_source_sha256"]=QUARTERLY_SHA
    if (out["fully_verified_nominal_share_rights"],out["unknown_share_rights"])!=(44,45):
        raise AssertionError("Exactly one source-complete event expected")
    output=(json.dumps(out,ensure_ascii=False,indent=2)+"\n").encode()
    audit={
        "kind":AUDIT_KIND,"frozen_exp018_catalog_full_sha256":BASE_SHA256,
        "derived_exp021_catalog_full_sha256":hashlib.sha256(output).hexdigest(),
        "primary_issuer_original_full_sha256s_verified":checked,
        "additional_full_original_quarterly_pdf_sha256_verified":1,
        "before_complete_unresolved":[43,46],"after_complete_unresolved":[44,45],
        "previously_unknown_bonus_fields_resolved":1,
        "previously_verified_transfer_fields_unchanged":89,
        "other_event_rows_fully_unchanged":88,
        "original_pdfs_prior_catalogs_or_frozen_returns_modified":False,
        "actual_broker_shares_cash_credit_or_execution_proven":False,
        "as_published_factor_and_amendment_chain_proven":False,
        "source_proof":proof,
    }
    out_dir.mkdir(parents=True)
    (out_dir/"rights_catalog_exp021.json").write_bytes(output)
    (out_dir/"source_audit.json").write_text(
        json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return audit


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-catalog",type=Path,required=True)
    p.add_argument("--issuer-pdfs",type=Path,nargs="+",required=True)
    p.add_argument("--quarterly-original-pdf",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.parent_catalog,a.issuer_pdfs,
                         a.quarterly_original_pdf,a.out_dir),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
