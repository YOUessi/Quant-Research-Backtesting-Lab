"""EXP022: issuer-hosted 3-document chain proves only capital-transfer zero.

An earlier board cash-dividend plan has no implementation force until AGM
approval; a meeting approval is linked to a later issuer implementation notice.
Two exact HXB A-stock events may gain transfer=0 while bonus remains UNKNOWN.
No generic absence-of-bonus inference or issuer/broker execution assertion.
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO
import json
from pathlib import Path

from pypdf import PdfReader

from .pit_share_distribution import clean
from .pit_exp019_unresolved_rights_negative import source_inventory

PARENT_SHA = "db49d725ffb28308c718a44521be11c304bed3ae5d386cc44f718117c5e50147"
PARENT_KIND = "EXP021_CROSS_ISSUER_NOTICES_RESOLVED_BONUS_CATALOG"
RESULT_KIND = "EXP022_HXB_APPROVED_NO_TRANSFER_PARTIAL_RIGHTS_CATALOG"
AUDIT_KIND = "EXP022_HXB_ISSUER_PLAN_AGM_FINAL_NO_TRANSFER_SOURCE_AUDIT"
GRADE = "ISSUER_PLAN_AGM_APPROVED_FINAL_IMPLEMENTATION_TRANSFER_ZERO_EXP022"
SYMBOL = "SH600015"
BASE_SHARES = "15,387,223,983"
ALL_YEARS = {
    "2021": {
        "fiscal": "2020", "ex_date": "2021-07-09",
        "event_id": "c36059f27517749d2dcc6218",
        "cash": "0.301", "cash_per_ten": "3.01",
        "agm_date": "2021年5月28日", "board_date": "2021年4月28日",
        "plan_original_date": "2021年4月30日",
        "agm_original_date": "2021年5月29日",
        "implementation_date": "2021年7月5日",
        "issuer_site_plan_day": "2021-04-30",
        "issuer_site_agm_day": "2021-06-01",
        "issuer_site_current_day": "2021-07-05",
        "conservative_plan_usable_day": "2021-05-06",
        "conservative_agm_usable_day": "2021-06-02",
        "conservative_final_usable_day": "2021-07-06",
        "proposal_title": "华夏银行股份有限公司2020年度利润分配预案",
        "approval_prefix": "本次利润分配方案经本公司2021年5月28日的2020年年度股东大会审议通过",
        "plan_filename": "SH600015_20210430_2020_year_plan_hxb.pdf",
        "plan_sha": "a88f3c5497bfbd082ec792a4ed4fa51c20896b50550e402cf6630c25629ea56d",
        "plan_url": "https://www.hxb.com.cn/hxb/articleFileDir/2021-04/30/c4ec5c39b9ad4cffa5a725dd630fcf10.pdf",
        "agm_filename": "SH600015_20210601_2020_year_agm_hxb.pdf",
        "agm_sha": "41e8dd72bffba80f149d81dc1a002e5b6b825516421ec4358685533ea3b1ed4b",
        "agm_url": "https://www.hxb.com.cn/hxb/articleFileDir/2021-06/01/2e69e6f82ad844bb999ff9360b57d408.pdf",
        "current_filename": "SH600015_20210705_2020_year_current_hxb.pdf",
        "current_sha": "0f1c725e105c0531c51644a3a2050f06908aa05742ea94b0796b25d1a8ddf1fa",
        "current_url": "https://www.hxb.com.cn/hxb/articleFileDir/2021-07/05/223e61dd62cc42c281cd39598baeb49e.pdf",
    },
    "2022": {
        "fiscal": "2021", "ex_date": "2022-06-08",
        "event_id": "7c5149184e10b18b4674b13b",
        "cash": "0.338", "cash_per_ten": "3.38",
        "implementation_cash_literal": "每股派发现金红利人民币0.338元（含税）",
        "agm_date": "2022年5月20日", "board_date": "2022年4月28日",
        "plan_original_date": "2022年4月30日",
        "agm_original_date": "2022年5月21日",
        "implementation_date": "2022年5月30日",
        "issuer_site_plan_day": "2022-05-05",
        "issuer_site_agm_day": "2022-05-23",
        "issuer_site_current_day": "2022-05-30",
        "conservative_plan_usable_day": "2022-05-06",
        "conservative_agm_usable_day": "2022-05-24",
        "conservative_final_usable_day": "2022-05-31",
        "proposal_title": "华夏银行2021年度利润分配预案",
        "approval_prefix": "本次利润分配方案经公司2022年5月20日的2021年年度股东大会审议通过",
        "plan_filename": "SH600015_20220505_2021_year_plan_hxb.pdf",
        "plan_sha": "6de4f0e3c69126f32fc14b939b65c19638f1bcffd320e3d44ef7f3d6822f614f",
        "plan_url": "https://www.hxb.com.cn/hxb/articleFileDir/2022-05/05/ac10c9c5a7584ccaba0f26afa5e8a841.pdf",
        "agm_filename": "SH600015_20220523_2021_year_agm_hxb.pdf",
        "agm_sha": "f6f710ffa519ac4f712df26947e9f41a6ed84d9d55c8c7c1ee289b32bf02ab9c",
        "agm_url": "https://www.hxb.com.cn/hxb/articleFileDir/2022-05/23/12240e3c2e374ced878818803057427b.pdf",
        "current_filename": "SH600015_20220530_2021_year_current_hxb.pdf",
        "current_sha": "1ad0a1fc1f0f00461c6822eed4e6547e5d9f96bfe1b7b752e11d044fbaae0e98",
        "current_url": "https://www.hxb.com.cn/hxb/articleFileDir/2022-05/30/a584373682d047f28ca2ad90ccaf442f.pdf",
    }
}
FROZEN_ROW_FIELDS = (
    "event_id", "symbol", "announcement_day", "earliest_usable_exchange_day",
    "record_date", "ex_date", "scheduled_cash_payment_day",
    "gross_cash_per_old_nominal_share", "issuer_original_pdf_sha256",
    "issuer_original_pdf_url", "bonus_shares_per_old_share",
    "full_new_nominal_share_multiplier", "complete_rights_supported_by_issuer_original",
    "cash_rights_nominal_not_qlib_adjusted",
    "broker_share_delivery_and_cash_payment_verified",
    "historical_factor_vintage_available",
    "original_publication_intraday_time_certified",
)


def extract_original_pdf(blob: bytes, expected_sha: str) -> tuple[str, str]:
    if not blob.startswith(b"%PDF") or hashlib.sha256(blob).hexdigest() != expected_sha:
        raise ValueError("Issuer original PDF whole-file SHA256/content mismatch")
    reader = PdfReader(BytesIO(blob), strict=False)
    if not reader.pages or len(reader.pages) > 100:
        raise ValueError("Issuer PDF empty/unexpected large page count")
    first = clean(reader.pages[0].extract_text() or "")
    body = clean("".join(page.extract_text() or "" for page in reader.pages))
    if not first or not body:
        raise ValueError("Issuer source original is not extractable")
    return first, body


def check_scoped_chain(
    cfg: dict, plan_first: str, plan_text: str, agm_first: str,
    agm_text: str, current_first: str, current_text: str
) -> None:
    """Require all 3 *specific original A-stock* documents, not token absence."""
    fy = cfg["fiscal"]
    if not (
        "A股代码：600015" in plan_first
        and f"华夏银行股份有限公司{fy}年度利润分配方案公告" in plan_first
        and cfg["plan_original_date"] in plan_text[-170:]
        and cfg["board_date"] in plan_text
    ):
        raise ValueError("Wrong original issuer board-plan identity/publication")
    if not (
        "证券代码：600015" in agm_first
        and f"华夏银行股份有限公司{fy}年年度股东大会决议公告" in agm_first
        and cfg["agm_date"] in agm_text
        and cfg["agm_original_date"] in agm_text[-180:]
    ):
        raise ValueError("Wrong original issuer AGM identity/approval clock")
    if not (
        "证券代码：600015" in current_first
        and f"华夏银行股份有限公司{fy}年年度权益分派实施公告" in current_first
        and cfg["implementation_date"] in current_text[-170:]
    ):
        raise ValueError("Wrong final issuer implementation A-stock/fiscal identity")

    p0 = plan_text.find("一、利润分配方案")
    p1 = plan_text.find("二、本年度现金分红比例", p0)
    if p0 < 0 or p1 <= p0:
        raise ValueError("Scoped board plan missing")
    proposal = plan_text[p0:p1]
    explicit_zero = f"（五）{fy}年度，本公司不实施资本公积金转增股本"
    if not (
        explicit_zero in proposal
        and f"每10股派发现金红利{cfg['cash_per_ten']}元（含税）" in proposal
        and BASE_SHARES + "股" in proposal
    ):
        raise ValueError("Literal no-transfer and matching cash/base missing in plan")
    if f"本次利润分配方案尚待本公司{fy}年年度股东大会审议通过后方可实施" not in plan_text:
        raise ValueError("Plan not explicitly marked pending approval")

    marker = "4、议案名称：《" + cfg["proposal_title"] + "》"
    a0 = agm_text.find(marker)
    a1 = agm_text.find("5、议案名称：", a0)
    if a0 < 0 or a1 <= a0:
        raise ValueError("Wrong AGM named motion or voting section")
    motion = agm_text[a0:a1]
    if not (
        "审议结果：通过" in motion
        and BASE_SHARES + "股" in motion
        and f"每10股现金分红{cfg['cash_per_ten']}元（含税）" in motion
    ):
        raise ValueError("AGM did not approve the matching named complete plan")

    c0 = current_text.find("一、通过分配方案的股东大会届次和日期")
    c1 = current_text.find("三、相关日期", c0)
    if c0 < 0 or c1 <= c0:
        raise ValueError("Final original implementation section missing")
    current = current_text[c0:c1]
    if not (
        cfg["approval_prefix"] in current
        and BASE_SHARES + "股" in current
        and cfg.get("implementation_cash_literal", f"每股派发现金红利{cfg['cash']}元（含税）") in current
    ):
        raise ValueError("Final implementation not linked to AGM approved terms")


def verify_event_chain(cfg: dict, row: dict, folder: Path) -> dict:
    if (
        row.get("symbol") != SYMBOL or row.get("event_id") != cfg["event_id"]
        or row.get("ex_date") != cfg["ex_date"]
        or row.get("issuer_original_pdf_sha256") != cfg["current_sha"]
        or row.get("announcement_day") != cfg["issuer_site_current_day"]
        or row.get("earliest_usable_exchange_day") != cfg["conservative_final_usable_day"]
    ):
        raise ValueError("Unapproved original event identity/publication clock")
    try:
        nominal_cash = Decimal(str(row.get("gross_cash_per_old_nominal_share")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Unparseable prior cash entitlement") from exc
    if not (
        row.get("complete_rights_supported_by_issuer_original") is False
        and row.get("bonus_shares_per_old_share") is None
        and row.get("capital_transfer_shares_per_old_share") is None
        and row.get("full_new_nominal_share_multiplier") is None
        and row.get("rights_evidence", {}).get("bonus") == "BONUS_UNCONFIRMED"
        and row.get("rights_evidence", {}).get("transfer") == "TRANSFER_UNCONFIRMED"
        and nominal_cash == Decimal(cfg["cash"])
    ):
        raise ValueError("Prior unknown bonus/transfer and cash mismatch")
    if any(row.get(k) is not False for k in (
        "broker_share_delivery_and_cash_payment_verified",
        "historical_factor_vintage_available",
        "original_publication_intraday_time_certified"
    )):
        raise ValueError("Already verified broker/vintage/intraday flags inconsistent")
    for name in ("plan", "agm", "current"):
        url = cfg[name+"_url"]
        if not url.startswith("https://www.hxb.com.cn/hxb/articleFileDir/"):
            raise ValueError("Non-issuer hosted source URL")
        if cfg["issuer_site_"+name+"_day"] not in url.replace("/", "-"):
            # Source website directory encodes only YYYY-MM/DD; compare separately.
            yy, mm, dd = cfg["issuer_site_"+name+"_day"].split("-")
            if f"/{yy}-{mm}/{dd}/" not in url:
                raise ValueError("Issuer website date/path mismatch")
    if cfg["issuer_site_plan_day"] >= cfg["issuer_site_agm_day"] or cfg["issuer_site_agm_day"] >= cfg["issuer_site_current_day"]:
        raise ValueError("Original issuer source chain not chronological")
    if not (cfg["conservative_plan_usable_day"] < cfg["conservative_agm_usable_day"] <
            cfg["conservative_final_usable_day"] < cfg["ex_date"]):
        raise ValueError("Future/incorrect source-use chronology")
    texts = {}
    for kind in ("plan", "agm", "current"):
        path = folder / cfg[kind+"_filename"]
        texts[kind] = extract_original_pdf(path.read_bytes(), cfg[kind+"_sha"])
    check_scoped_chain(cfg, *texts["plan"], *texts["agm"], *texts["current"])
    return {
        "symbol": SYMBOL, "event_id": cfg["event_id"], "ex_date": cfg["ex_date"],
        "source_grade": GRADE,
        "original_issuer_sources": [
            {
                "role": part,
                "original_url": cfg[part+"_url"],
                "whole_pdf_sha256": cfg[part+"_sha"],
                "conservative_issuer_website_listing_day": cfg["issuer_site_"+part+"_day"],
                "original_internal_document_date": cfg[{"plan":"plan_original_date","agm":"agm_original_date","current":"implementation_date"}[part]],
                "conservative_first_usable_trading_day": cfg["conservative_"+{"plan":"plan","agm":"agm","current":"final"}[part]+"_usable_day"]
            }
            for part in ("plan", "agm", "current")
        ],
        "issuer_approved_capital_transfer_per_old_share": "0",
        "gross_cash_per_old_share_cny_unchanged": cfg["cash"],
        "explicit_bonus_zero_claim": False,
        "actual_broker_credit_or_shares_sellable_verified": False,
        "historical_factor_vintage_confirmed": False,
        "source_amendment_exhaustiveness_verified": False,
    }


def apply_partial_transfer_proof(row: dict, proof: dict) -> dict:
    if not (
        proof.get("source_grade") == GRADE
        and proof.get("event_id") == row.get("event_id")
        and proof.get("issuer_approved_capital_transfer_per_old_share") == "0"
        and proof.get("explicit_bonus_zero_claim") is False
        and row.get("capital_transfer_shares_per_old_share") is None
        and row.get("bonus_shares_per_old_share") is None
        and row.get("complete_rights_supported_by_issuer_original") is False
    ):
        raise ValueError("Forged or unsupported partial transfer proof")
    before = copy.deepcopy(row)
    after = copy.deepcopy(row)
    after["capital_transfer_shares_per_old_share"] = 0.0
    after["rights_evidence"]["transfer"] = GRADE
    after["exp022_issuer_approved_no_transfer_chain"] = copy.deepcopy(proof)
    if any(after[k] != before[k] for k in FROZEN_ROW_FIELDS):
        raise AssertionError("Attempted change to unrelated economics, bonus, broker or time")
    assert after["bonus_shares_per_old_share"] is None
    assert after["full_new_nominal_share_multiplier"] is None
    assert after["complete_rights_supported_by_issuer_original"] is False
    return after


def run(parent_catalog: Path, source_dirs: list[Path], issuer_folder: Path, outdir: Path) -> dict:
    if outdir.exists():
        raise FileExistsError("Never overwrite old source, audit, catalog or output directory")
    raw = parent_catalog.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("Wrong exact frozen EXP021 parent catalog")
    parent = json.loads(raw)
    rows = parent["events"]
    if not (
        parent["kind"] == PARENT_KIND and len(rows) == 89
        and (parent["fully_verified_nominal_share_rights"], parent["unknown_share_rights"]) == (44, 45)
        and len({(x["symbol"],x["ex_date"]) for x in rows}) == 89
    ):
        raise ValueError("Wrong immutable parent source event coverage")
    originals, num = source_inventory(rows, source_dirs)
    assert num == 89
    byid = {x["event_id"]: x for x in rows}
    proofs = {}
    for year,cfg in ALL_YEARS.items():
        row = byid[cfg["event_id"]]
        proof = verify_event_chain(cfg,row,issuer_folder)
        if hashlib.sha256(originals[cfg["current_sha"]].read_bytes()).hexdigest() != cfg["current_sha"]:
            raise ValueError("Archived CNINFO original differs from exact issuer current")
        proofs[cfg["event_id"]] = proof
    updated = copy.deepcopy(parent)
    updated["kind"] = RESULT_KIND
    updated["source_exp021_catalog_sha256"] = PARENT_SHA
    updated["events"] = [
        apply_partial_transfer_proof(r,proofs[r["event_id"]])
        if r["event_id"] in proofs else copy.deepcopy(r)
        for r in rows
    ]
    updated["exp022_issuer_approved_partial_transfer_fields_resolved"] = 2
    updated["fully_verified_nominal_share_rights"] = sum(
        r["complete_rights_supported_by_issuer_original"] for r in updated["events"])
    updated["unknown_share_rights"] = 89 - updated["fully_verified_nominal_share_rights"]
    if (updated["fully_verified_nominal_share_rights"],updated["unknown_share_rights"]) != (44,45):
        raise AssertionError("Unverified bonus wrongly promoted to full share-rights")
    if sum(x == y for x,y in zip(rows,updated["events"])) != 87:
        raise AssertionError("Non-target original row changed")
    catalog_data = (json.dumps(updated,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    audit = {
        "kind": AUDIT_KIND,
        "frozen_exp021_source_catalog_full_sha256": PARENT_SHA,
        "new_derived_exp022_catalog_full_sha256": hashlib.sha256(catalog_data).hexdigest(),
        "primary_issuer_original_full_sha256_checked": num,
        "additional_issuer_hosted_original_full_sha256_checked": 6,
        "fully_source_verified_rights_before_after": [44,44],
        "unresolved_bonus_or_share_rights_before_after": [45,45],
        "issuer_approved_capital_transfer_zero_newly_resolved": 2,
        "unknown_bonus_fields_still_unknown_for_targets": 2,
        "other_event_rows_fully_unchanged": 87,
        "legacy_cash_publication_broker_and_model_data_modified": False,
        "actual_broker_delivery_or_auction_fill_proven": False,
        "historical_factor_vintage_or_complete_amendment_chain_proven": False,
        "strict_approval_links": [proofs[k] for k in sorted(proofs)],
    }
    outdir.mkdir(parents=True,exist_ok=False)
    (outdir/"rights_catalog_exp022.json").write_bytes(catalog_data)
    (outdir/"source_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-catalog",type=Path,required=True)
    parser.add_argument("--issuer-pdfs",type=Path,nargs="+",required=True)
    parser.add_argument("--issuer-original-folder",type=Path,required=True)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    result=run(args.parent_catalog,args.issuer_pdfs,args.issuer_original_folder,args.out_dir)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
