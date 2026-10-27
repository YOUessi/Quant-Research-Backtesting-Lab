"""EXP023: original SPDB annual dividend matrix -> approved cash-only stock rights.

This is a deliberately issuer-specific source chain, NOT a general method
that considers an annual report, proposal, silence or stable share count
sufficient by itself to prove cash-only distribution.

Source hierarchy:
  original issuer annual report's YEAR-EXACT per-ten-share columns:
    bonus shares = DASH, gross cash = 4.80 / 4.10 CNY, capital transfer = DASH
  issuer board's proposed corresponding fiscal-year distribution;
  pre-AGM meeting agenda listing the exact fiscal-year cash proposal;
  issuer ORIGINAL annual general meeting resolution approving the proposal;
  issuer original final 2021/2022 A-share implementation referencing that AGM
  with same cash per OLD share, accurate record/ex and actual dividend base.

A DASH in the explicit numeric annual-report table is accepted only after
the whole approved implementation chain passes. This does NOT establish
exhaustive historical corrections, payment at the holder's broker, security
exchange price-limit conditions, or original-source exact intraday publication.

All originals must match full SHA256 and known CNINFO historical URLs.
Raw original PDF bytes remain gitignored on the authorized Mac.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader

from .pit_exp019_unresolved_rights_negative import source_inventory

PARENT_SHA = "b29464c49a2e1abc7241d2e8148ccd00bd110e8b55b868726d6810e096873c00"
PARENT_KIND = "EXP022_HXB_APPROVED_NO_TRANSFER_PARTIAL_RIGHTS_CATALOG"
KIND = "EXP023_SPDB_ORIGINAL_ANNUAL_AGM_FINAL_CASH_ONLY_RIGHTS_CATALOG"
AUDIT_KIND = "EXP023_SPDB_2020_2021_APPROVED_ANNUAL_CASH_ONLY_PRIMARY_PDF_AUDIT"
GRADE = "SOURCE_ANNUAL_TABLE_ZERO_BONUS_AND_TRANSFER_APPROVED_AGM_MATCHED_FINAL"
TICKER = "SH600000"

SOURCES = {
    "2020": {
        "key": "2021", "fiscal": "2020", "annual_page": 52,
        "target_event_id": "add4bd8b25db659099f2af93",
        "record": "2021-07-20", "ex": "2021-07-21",
        "cash_per_ten": "4.80", "cash_per_share": "0.48",
        "distribution_base": "29352160584",
        "expected_gross_distributed_cash": "14089037080.32",
        "agm_held": "2021年6月11日",
        "agm_materials_page": 16, "agm_resolution_page": 2,
        "annual": (
            "2021_2020_annual_original.pdf",
            "ae8771ef6f64f06cf1de27e7adb10309b5a1a21c701e2eee4ea4734c56550164",
            "2021-03-27", "1209565322.PDF",
        ),
        "board": (
            "2021_2020_board_profit.pdf",
            "cb9a7a73bcdad11f4c0bc410d57e0ebf291bfecc547243acbaef11f886e92851",
            "2021-03-27", "1209465959.PDF",
        ),
        "agm_materials": (
            "2021_2020_AGM_materials.pdf",
            "1d2896fda63771e9e73f2e091c8708370a40b515cd70d310cfdd223111570d4a",
            "2021-06-04", "1210160923.PDF",
        ),
        "agm_resolution": (
            "2021_2020_AGM_resolution.pdf",
            "86894a63a461d655539c543c3bf520ad82ccbf88f1ec459a25aff6e4f9b09f93",
            "2021-06-12", "1210224472.PDF",
        ),
        "implementation": (
            "2021_2020_implementation.pdf",
            "fbadb95f0d82ebe980c559cb5bf5b8d4489b2b1e9374f585704a3719c79916ba",
            "2021-07-13", "1210467899.PDF",
        ),
    },
    "2021": {
        "key": "2022", "fiscal": "2021", "annual_page": 70,
        "target_event_id": "b3646f7ee0b5840b34523c72",
        "record": "2022-07-20", "ex": "2022-07-21",
        "cash_per_ten": "4.10", "cash_per_share": "0.41",
        "distribution_base": "29352173289",
        "expected_gross_distributed_cash": "12034391048.49",
        "agm_held": "2022年6月17日",
        "agm_materials_page": 15, "agm_resolution_page": 2,
        "annual": (
            "2022_2021_annual_original.pdf",
            "6bd3d544902c1f4568e9f1336f0585602889e61a69a88afc541f53bfd8091332",
            "2022-04-28", "1213175151.PDF",
        ),
        "board": (
            "2022_2021_board_profit.pdf",
            "17dc4c7060082cb0707ac0df27977d661a350e0af53966384788345b1bd5fda8",
            "2022-04-28", "1213175146.PDF",
        ),
        "agm_materials": (
            "2022_2021_AGM_materials.pdf",
            "7e8e53ac007c655a3b99ef612c8e944cbe688e85015ba68c96b59fd8769e737a",
            "2022-06-11", "1213677295.PDF",
        ),
        "agm_resolution": (
            "2022_2021_AGM_resolution.pdf",
            "348e3024eb528eef3709e973e0593f837391d33d43d71e8d93ab65156bcf47a4",
            "2022-06-18", "1213743642.PDF",
        ),
        "implementation": (
            "2022_2021_implementation.pdf",
            "2698706b68bbd5dbff734617a816fa27dfb72bf63f9e83113b7f78baf0664b92",
            "2022-07-13", "1214014565.PDF",
        ),
    },
}

FROZEN_FIELDS = (
    "event_id", "symbol", "announcement_day",
    "earliest_usable_exchange_day", "record_date", "ex_date",
    "scheduled_cash_payment_day", "gross_cash_per_old_nominal_share",
    "issuer_original_pdf_sha256", "issuer_original_pdf_url",
    "cash_rights_nominal_not_qlib_adjusted",
    "broker_share_delivery_and_cash_payment_verified",
    "original_publication_intraday_time_certified",
    "historical_factor_vintage_available",
)


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("Ａ", "A").replace("－", "－")


def _pdf(folder: Path, item: tuple, *, selected_page: int) -> dict:
    filename, sha, publication, suffix = item
    location = folder / filename
    if not location.is_file():
        raise FileNotFoundError(f"Missing original primary issuer source {filename}")
    raw = location.read_bytes()
    if not raw.startswith(b"%PDF") or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f"Original issuer PDF whole-file SHA256 check failed: {filename}")
    pdf = PdfReader(location, strict=False)
    if not (selected_page < len(pdf.pages) < 480):
        raise ValueError("Unexpected original annual/AGM source page count")
    first = norm(pdf.pages[0].extract_text() or "")
    selected = norm(pdf.pages[selected_page].extract_text() or "")
    if not selected:
        raise ValueError("Original source selected page text is not extractable")
    return {
        "first": first,
        "selected": selected,
        "filename": filename,
        "sha256": sha,
        "publication_day": publication,
        "source_url": f"https://static.cninfo.com.cn/finalpage/{publication}/{suffix}",
        "page_index": selected_page,
        "pdf_pages": len(pdf.pages),
    }


def _amount(value) -> Decimal:
    try:
        d = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValueError("Unparseable original issuer decimal money") from e
    if not d.is_finite() or d < 0:
        raise ValueError("Invalid issuer original cash figure")
    return d


def check_exact_annual_bonus_transfer_table(text: str, cfg: dict) -> dict:
    """A dash in BOTH explicitly named numeric columns; never absence-based."""
    fy, cash = cfg["fiscal"], cfg["cash_per_ten"]
    marker = "公司近三年的普通股股利分配方案或预案、资本公积转增股本方案或预案"
    i = text.find(marker)
    end = text.find(f"注：{fy}年度利润分配预案尚需股东大会审议批准后方可实施", i)
    if i < 0 or end <= i:
        raise ValueError("Annual plan table/proposal prior-to-approval scope missing")
    section = text[i:end]
    required = (
        "分红年度每10股送红股数（股）"
        "每10股派息数（元）（含税）"
        "每10股转增数（股）"
    )
    if required not in section:
        raise ValueError("Annual table lacks explicitly labeled bonus/cash/transfer fields")
    exact = f"{fy}年-{cash}-"
    rows = re.findall(
        rf"{fy}年(?:-|[0-9]+(?:\.[0-9]+)?)(?:[0-9]+(?:\.[0-9]+)?)(?:-|[0-9]+(?:\.[0-9]+)?)",
        section,
    )
    if len(rows) != 1 or rows[0] != exact:
        raise ValueError("Exact fiscal annual approved-proposal per-ten bonus/cash/transfer DASH not established")
    if f"{fy}年度利润分配" not in text[end:]:
        raise ValueError("Same annual original has no corresponding fiscal proposal")
    return {
        "issuer_table_fiscal_year": fy,
        "source_row": exact,
        "proposal_bonus_per_10": "0_AS_SOURCE_DASH",
        "proposal_capital_transfer_per_10": "0_AS_SOURCE_DASH",
        "gross_cash_per_ten_original_table": cash,
        "board_plan_only_until_AGM": True,
        "not_by_itself_implemented": True,
    }


def verify_five_original_issuer_documents(cfg: dict, documents: dict[str,dict]) -> dict:
    fy = cfg["fiscal"]
    annual = documents["annual"]["selected"]
    board = documents["board"]["selected"]
    material = documents["agm_materials"]["selected"]
    agm = documents["agm_resolution"]["selected"]
    implemented = documents["implementation"]["selected"]
    annual_proof = check_exact_annual_bonus_transfer_table(annual, cfg)
    for part in ("board","agm_resolution","implementation"):
        if "证券代码：600000" not in documents[part]["first"]:
            raise ValueError("Original issuer A-share 600000 stock label mismatched")
        expected_title = (
            f"上海浦东发展银行股份有限公司{fy}年年度股东大会决议公告"
            if part == "agm_resolution" else
            f"上海浦东发展银行股份有限公司{fy}年度"
        )
        if expected_title not in documents[part]["first"]:
            raise ValueError("Wrong year or issuer official document title")
    if f"上海浦东发展银行股份有限公司{fy}年年度股东大会会议资料" not in documents["agm_materials"]["first"]:
        raise ValueError("Wrong annual AGM materials original identity")
    if f"{fy}年度利润分配方案公告" not in board:
        raise ValueError("Issuer board's exact fiscal proposal missing")
    if not re.search(rf"每股派发现金股利人民币{re.escape(cfg['cash_per_share'])}元（含税）", board):
        raise ValueError("Issuer board cash ratio inconsistent with annual table")
    if f"本次利润分配方案尚待公司{fy}年年度股东大会审议通过后方可实施" not in board:
        raise ValueError("Board original not explicitly pending shareholder approval")
    if f"议案四：上海浦东发展银行股份有限公司{fy}年度利润分配的预案" not in material:
        raise ValueError("Published AGM material does not contain same named fiscal dividend motion")
    if not re.search(
        rf"每10股派送现金股利{re.escape(str(_amount(cfg['cash_per_ten']).normalize()))}元人民币（含税）",
        material,
    ):
        raise ValueError("AGM original material's cash ratio is not the same fiscal plan")
    approve = f"4、议案名称：公司{fy}年度利润分配的预案审议结果：通过公司{fy}年度利润分配方案如下"
    s = agm.find(approve)
    if s < 0:
        raise ValueError("No source-original shareholder-approved named fiscal plan")
    next_item = agm.find("5、议案名称：", s)
    vote = agm[s:next_item if next_item > s else s + 750]
    normalized_cash = cfg["cash_per_ten"]
    options = [normalized_cash, str(_amount(normalized_cash).normalize())]
    if not any(
        re.search(rf"每10股(?:派发|派送)现金股利人民币{re.escape(val)}元（含税）",vote)
        for val in options
    ):
        raise ValueError("Approved shareholder motion has wrong annual gross cash")
    if not f"上海浦东发展银行股份有限公司{fy}年度普通股分红派息实施公告" in implemented:
        raise ValueError("Final current A-share source has wrong fiscal event identity")
    if f"{cfg['agm_held']}召开的{fy}年年度股东大会审议通过" not in implemented:
        raise ValueError("Current source does not link precise approved AGM")
    if f"每股现金红利人民币{cfg['cash_per_share']}元（含税）" not in implemented:
        raise ValueError("Current implementation cash disagrees with annual approved scheme")
    if "差异化分红送转：否" not in implemented:
        raise ValueError("Current source has changed differential-distribution status")
    def pdf_date_iso(iso):
        stamp = pd.Timestamp(iso)
        return f"{stamp.year}/{stamp.month}/{stamp.day}"
    record, ex = (pdf_date_iso(cfg["record"]), pdf_date_iso(cfg["ex"]))
    if f"A股{record}－{ex}{ex}" not in implemented:
        raise ValueError("Current issuer original record/ex/pay dates diverged")
    # Exact A-share implementation share base is not required to equal the
    # previous fiscal-year-end base because convertible-bond exercise changes it.
    base = cfg["distribution_base"]
    amount = cfg["expected_gross_distributed_cash"]
    if not re.search(
        rf"本次利润分配以方案实施前的公司(?:普通股)?总股本{int(base):,}股为基数，"
        rf"每股派发现金红利人民币{re.escape(cfg['cash_per_share'])}元（含税），"
        rf"共计派发现金红利人民币{re.escape(f'{_amount(amount):,.2f}')}元（含税）",
        implemented,
    ):
        raise ValueError("Final issuer share base, per-share cash or aggregate cash inconsistent")
    if _amount(base) * _amount(cfg["cash_per_share"]) != _amount(amount):
        raise ValueError("Final issuer cash/base exact Decimal arithmetic inconsistent")
    return {
        **annual_proof,
        "agm_resolution_approved_same_fiscal_cash_scheme": True,
        "final_issuer_current_approved_annual_cash_matched": True,
        "final_actual_issuer_dividend_base": base,
        "final_cash_gross_total": amount,
        "share_base_changes_due_to_convertibles_not_used_as_no_bonus_evidence": True,
        "zero_bonus_and_transfer_source_grade": GRADE,
        "complete_corporate_actions_amendment_history_verified": False,
        "individual_broker_new_shares_or_cash_credited": False,
    }


def verify_event(row: dict, cfg: dict, folder: Path, calendar: list[str]) -> dict:
    if not (
        row["symbol"] == TICKER
        and row["event_id"] == cfg["target_event_id"]
        and row["record_date"] == cfg["record"]
        and row["ex_date"] == cfg["ex"]
        and row["announcement_day"] == cfg["implementation"][2]
        and row["issuer_original_pdf_sha256"] == cfg["implementation"][1]
        and row["issuer_original_pdf_url"] ==
            f"https://static.cninfo.com.cn/finalpage/{cfg['implementation'][2]}/{cfg['implementation'][3]}"
        and _amount(row["gross_cash_per_old_nominal_share"]) == _amount(cfg["cash_per_share"])
        and row["bonus_shares_per_old_share"] is None
        and row["capital_transfer_shares_per_old_share"] is None
        and row["full_new_nominal_share_multiplier"] is None
        and row["complete_rights_supported_by_issuer_original"] is False
        and row["rights_evidence"]["bonus"] == "BONUS_UNCONFIRMED"
        and row["rights_evidence"]["transfer"] == "TRANSFER_UNCONFIRMED"
    ):
        raise ValueError("Wrong frozen issuer event or already known cash/share-rights")
    time_sources = [cfg[x][2] for x in
                    ("annual","board","agm_materials","agm_resolution","implementation")]
    if time_sources != sorted(time_sources) or len(set(time_sources)) != 4:
        # annual and board may have SAME day, all other source stages unique
        raise ValueError("Original issuer announcement calendar chain invalid")
    days = sorted(set(str(pd.Timestamp(day).date()) for day in calendar))
    use_days = []
    for d in time_sources:
        next_session = next((a for a in days if a > d),None)
        if next_session is None or next_session > cfg["record"]:
            raise ValueError("Historical original publication not usable before entitlement registration")
        use_days.append(next_session)
    if not (
        use_days[0] <= use_days[1] < use_days[2] < use_days[3] < use_days[4]
        and use_days[4] == row["earliest_usable_exchange_day"]
        and row["earliest_usable_exchange_day"] <= row["record_date"]
    ):
        raise ValueError("Original original issuer PIT date/time boundary mismatch")
    pages = {
        "annual": cfg["annual_page"],
        "board": 0,
        "agm_materials": cfg["agm_materials_page"],
        "agm_resolution": cfg["agm_resolution_page"],
        "implementation": 0,
    }
    docs = {k:_pdf(folder,cfg[k],selected_page=pages[k]) for k in pages}
    if docs["implementation"]["sha256"] != row["issuer_original_pdf_sha256"]:
        raise ValueError("Original archive and current source implementation full SHA256 mismatch")
    check = verify_five_original_issuer_documents(cfg, docs)
    return {
        "symbol": TICKER,
        "event_id":row["event_id"],
        "ex_date":row["ex_date"],
        "proof_grade": GRADE,
        "cash_per_old_share_unchanged": cfg["cash_per_share"],
        "issuer_proposal_approved_zero_bonus": "0",
        "issuer_proposal_approved_zero_capital_transfer": "0",
        "source_documents":[{
            "source_kind":k,"original_filename":docs[k]["filename"],
            "url":docs[k]["source_url"],
            "whole_sha256":docs[k]["sha256"],
            "publication_calendar_day":docs[k]["publication_day"],
            "conservative_usable_exchange_day":use_days[list(pages).index(k)],
            "pdf_pages":docs[k]["pdf_pages"],
            "verified_original_pdf_page_zero_indexed":docs[k]["page_index"],
        } for k in pages],
        **check,
        "not_original_historical_factor_vintage_certificate":True,
        "no_realtime_broker_corporate_credit_verified":True,
    }


def apply_cash_only_original_proof(row: dict, proof: dict) -> dict:
    if not (
        row["event_id"] == proof.get("event_id")
        and row["symbol"] == proof.get("symbol") == TICKER
        and row["ex_date"] == proof.get("ex_date")
        and proof.get("proof_grade") == GRADE
        and proof.get("issuer_proposal_approved_zero_bonus") == "0"
        and proof.get("issuer_proposal_approved_zero_capital_transfer") == "0"
        and row["bonus_shares_per_old_share"] is None
        and row["capital_transfer_shares_per_old_share"] is None
        and row["complete_rights_supported_by_issuer_original"] is False
    ):
        raise ValueError("Unproven original issuer event cannot gain zero share rights")
    before = deepcopy(row)
    after = deepcopy(row)
    after["bonus_shares_per_old_share"] = 0.0
    after["capital_transfer_shares_per_old_share"] = 0.0
    after["full_new_nominal_share_multiplier"] = 1.0
    after["complete_rights_supported_by_issuer_original"] = True
    after["rights_evidence"]["bonus"] = GRADE
    after["rights_evidence"]["transfer"] = GRADE
    after["exp023_approved_spdb_original_chain"] = deepcopy(proof)
    for k in FROZEN_FIELDS:
        if before.get(k) != after.get(k):
            raise AssertionError("Cash, historical source timing, issuer URL or broker flag changed")
    if (after["cash_rights_nominal_not_qlib_adjusted"] is not True
        or after["broker_share_delivery_and_cash_payment_verified"] is not False
        or after["original_publication_intraday_time_certified"] is not False
        or after["historical_factor_vintage_available"] is not False):
        raise AssertionError("Accidental upgrade of real broker or historical vintage claim")
    return after


def audit_catalog(parent_path: Path, issuer_original_folder: Path,
                  all_issuer_dirs: list[Path], calendar_file: Path) -> tuple[dict, dict]:
    original_bytes=parent_path.read_bytes()
    sha=hashlib.sha256(original_bytes).hexdigest()
    if sha != PARENT_SHA:
        raise ValueError("Frozen EXP022 parent source catalog whole-byte SHA256 mismatch")
    parent=json.loads(original_bytes)
    old=parent["events"]
    if (parent["kind"] != PARENT_KIND
        or parent["fully_verified_nominal_share_rights"] != 44
        or parent["unknown_share_rights"] != 45
        or len(old) != 89
        or len({r["event_id"] for r in old}) != 89):
        raise ValueError("Parent original-share event state not frozen EXP022")
    files, count=source_inventory(old,all_issuer_dirs)
    if count != 89:raise AssertionError("89 original issuer implementation PDFs not verified")
    calendar=pd.read_csv(calendar_file,header=None)[0].astype(str).tolist()
    by_id={r["event_id"]:r for r in old}
    approvals={}
    for fiscal,cfg in SOURCES.items():
        approvals[cfg["target_event_id"]]=verify_event(
            by_id[cfg["target_event_id"]],cfg,issuer_original_folder,calendar
        )
        if files[cfg["implementation"][1]].read_bytes() != (
            issuer_original_folder/cfg["implementation"][0]).read_bytes():
            raise ValueError("Archived original and new issuer implementation PDF bytes differ")
    new=deepcopy(parent)
    new["kind"]=KIND
    new["exp023_parent_original_catalog_full_SHA256"]=PARENT_SHA
    new["events"]=[
        apply_cash_only_original_proof(r,approvals[r["event_id"]])
        if r["event_id"] in approvals else deepcopy(r)
        for r in old
    ]
    before_by_id={r["event_id"]:r for r in old}
    for r in new["events"]:
        if r["event_id"] not in approvals and r != before_by_id[r["event_id"]]:
            raise AssertionError("Non-target original issuer event changed")
    after_complete=sum(r["complete_rights_supported_by_issuer_original"] for r in new["events"])
    if after_complete != 46:
        raise AssertionError("Only exact 2 cash-only events may be upgraded")
    new["fully_verified_nominal_share_rights"]=46
    new["unknown_share_rights"]=43
    new["exp023_full_cash_only_original_events_newly_proven"]=2
    new_bytes=(json.dumps(new,ensure_ascii=False,indent=2)+"\n").encode()
    audit={
        "kind":AUDIT_KIND,
        "parent_original_catalog_sha256":PARENT_SHA,
        "derived_new_catalog_sha256":hashlib.sha256(new_bytes).hexdigest(),
        "original_issuer_implementation_PDFs_whole_sha256_verified":89,
        "additional_original_annual_approval_and_final_PDFs_verified":10,
        "original_full_rights_before_after":[44,46],
        "original_unresolved_rights_before_after":[45,43],
        "source_table_zero_bonus_and_transfer_newly_complete":2,
        "other_source_event_rows_fully_unchanged":87,
        "all_originals_chronology_approved_final":True,
        "historical_factor_vintage_or_all_amendment_chain_verified":False,
        "broker_cash_stock_credits_or_executable_trade_verified":False,
        "past_model_prices_positions_and_returns_unchanged":True,
        "derived_cash_only_approved_issuer_proofs":[
            approvals[k] for k in sorted(approvals)
        ],
    }
    return new,audit


def run(parent_catalog:Path, original_folder:Path, all_issuer_dirs:list[Path],
        calendar:Path,outdir:Path)->dict:
    if outdir.exists():
        raise FileExistsError("Refusing to overwrite original/frozen issuer evidence output")
    child,audit=audit_catalog(parent_catalog,original_folder,all_issuer_dirs,calendar)
    outdir.mkdir(parents=True,exist_ok=False)
    c=outdir/"rights_catalog_exp023.json"
    a=outdir/"source_audit.json"
    c.write_text(json.dumps(child,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    a.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if hashlib.sha256(c.read_bytes()).hexdigest()!=audit["derived_new_catalog_sha256"]:
        raise AssertionError("Derived source audit reports different catalog bytes")
    return audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-catalog",type=Path,required=True)
    p.add_argument("--source-original-folder",type=Path,required=True)
    p.add_argument("--archived-issuer-pdfs",type=Path,nargs="+",required=True)
    p.add_argument("--exchange-calendar",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    x=p.parse_args()
    audit=run(x.parent_catalog,x.source_original_folder,
              x.archived_issuer_pdfs,x.exchange_calendar,x.out_dir)
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
