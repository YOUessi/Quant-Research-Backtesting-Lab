"""Regression and original-byte adversarial tests for EXP022 partial transfer proof."""
from __future__ import annotations
import copy
from decimal import Decimal
from pathlib import Path

import pytest

from quant_lab.pit_exp022_issuer_approved_partial_transfer import (
    ALL_YEARS, GRADE, SYMBOL, PARENT_SHA, PARENT_KIND,
    check_scoped_chain, extract_original_pdf, verify_event_chain,
    apply_partial_transfer_proof, run,
)

SOURCE_FOLDER = Path("data/pit/exp022_exchange_original_20261028")
PARENT_CATALOG = Path("runs/exp021_full_replay_20261028_001/exp021/rights_catalog_exp021.json")


def fixture_row(cfg):
    return {
        "event_id": cfg["event_id"], "symbol": SYMBOL,
        "announcement_day": cfg["issuer_site_current_day"],
        "earliest_usable_exchange_day": cfg["conservative_final_usable_day"],
        "record_date": "2021-07-08" if cfg["ex_date"] == "2021-07-09" else "2022-06-07",
        "ex_date": cfg["ex_date"],
        "scheduled_cash_payment_day": cfg["ex_date"],
        "gross_cash_per_old_nominal_share": float(cfg["cash"]),
        "issuer_original_pdf_sha256": cfg["current_sha"],
        "issuer_original_pdf_url": cfg["current_url"],
        "bonus_shares_per_old_share": None,
        "capital_transfer_shares_per_old_share": None,
        "full_new_nominal_share_multiplier": None,
        "complete_rights_supported_by_issuer_original": False,
        "rights_evidence": {"bonus": "BONUS_UNCONFIRMED", "transfer": "TRANSFER_UNCONFIRMED"},
        "capital_issuer_balance_extra_proof": None,
        "positive_stock_rights": False,
        "cash_rights_nominal_not_qlib_adjusted": True,
        "broker_share_delivery_and_cash_payment_verified": False,
        "historical_factor_vintage_available": False,
        "original_publication_intraday_time_certified": False,
    }


def fixture_proof(cfg):
    return {
        "source_grade": GRADE, "event_id": cfg["event_id"],
        "issuer_approved_capital_transfer_per_old_share": "0",
        "explicit_bonus_zero_claim": False,
    }


@pytest.mark.parametrize("year", tuple(ALL_YEARS))
def test_partial_transfer_preserves_bonus_unknown_and_account_flags(year):
    cfg = ALL_YEARS[year]
    before=fixture_row(cfg)
    after=apply_partial_transfer_proof(before,fixture_proof(cfg))
    assert after["capital_transfer_shares_per_old_share"] == 0.
    assert after["rights_evidence"]["transfer"] == GRADE
    assert after["bonus_shares_per_old_share"] is None
    assert after["full_new_nominal_share_multiplier"] is None
    assert after["complete_rights_supported_by_issuer_original"] is False
    assert after["broker_share_delivery_and_cash_payment_verified"] is False
    assert after["historical_factor_vintage_available"] is False
    assert after["gross_cash_per_old_nominal_share"] == float(cfg["cash"])
    assert before["capital_transfer_shares_per_old_share"] is None


@pytest.mark.parametrize("year", tuple(ALL_YEARS))
@pytest.mark.parametrize("tamper", [
    "source_grade", "event_id", "issuer_approved_capital_transfer_per_old_share",
    "explicit_bonus_zero_claim",
])
def test_forged_partial_proof_rejected(year,tamper):
    cfg=ALL_YEARS[year]
    p=fixture_proof(cfg)
    p[tamper]=("UNVERIFIED" if tamper!="explicit_bonus_zero_claim" else True)
    with pytest.raises(ValueError):
        apply_partial_transfer_proof(fixture_row(cfg),p)


@pytest.mark.parametrize("year", tuple(ALL_YEARS))
@pytest.mark.parametrize("tamper", [
    "bonus_shares_per_old_share", "capital_transfer_shares_per_old_share",
    "complete_rights_supported_by_issuer_original",
])
def test_preexisting_share_rights_not_overridden(year,tamper):
    cfg=ALL_YEARS[year]
    r=fixture_row(cfg)
    r[tamper]=1 if tamper!="complete_rights_supported_by_issuer_original" else True
    with pytest.raises(ValueError):
        apply_partial_transfer_proof(r,fixture_proof(cfg))


@pytest.mark.parametrize("year",tuple(ALL_YEARS))
@pytest.mark.parametrize("tamper", [
    "symbol","event_id","ex_date","issuer_original_pdf_sha256",
    "announcement_day","earliest_usable_exchange_day",
    "gross_cash_per_old_nominal_share",
    "original_publication_intraday_time_certified",
])
def test_source_row_identity_asof_cash_or_broker_conflicts_rejected(year,tamper):
    cfg=ALL_YEARS[year]
    r=fixture_row(cfg)
    if tamper == "original_publication_intraday_time_certified":
        r[tamper]=True
    else:
        r[tamper]="INVALID"
    with pytest.raises(ValueError):
        verify_event_chain(cfg,r,SOURCE_FOLDER)


@pytest.mark.parametrize("year", tuple(ALL_YEARS))
def test_real_issuer_approved_three_source_chain(year):
    cfg=ALL_YEARS[year]
    if not all((SOURCE_FOLDER/cfg[k+"_filename"]).is_file() for k in ("plan","agm","current")):
        pytest.skip("Issuer originals absent (original-only Mac replay checks originals)")
    proof=verify_event_chain(cfg,fixture_row(cfg),SOURCE_FOLDER)
    assert proof["issuer_approved_capital_transfer_per_old_share"] == "0"
    assert proof["explicit_bonus_zero_claim"] is False
    assert len(proof["original_issuer_sources"])==3
    assert not proof["historical_factor_vintage_confirmed"]
    assert not proof["actual_broker_credit_or_shares_sellable_verified"]


@pytest.mark.parametrize("year", tuple(ALL_YEARS))
def test_original_pdf_tamper_rejected(year):
    cfg=ALL_YEARS[year]
    pdf=SOURCE_FOLDER/cfg["plan_filename"]
    if not pdf.is_file():
        pytest.skip("Issuer original source not checked into Git")
    body=pdf.read_bytes()
    with pytest.raises(ValueError,match="SHA256"):
        extract_original_pdf(body+b"\x00",cfg["plan_sha"])


@pytest.mark.parametrize("year",tuple(ALL_YEARS))
@pytest.mark.parametrize("tamper",[
    "delete_literal_no_transfer","swap_AGM_approval","erase_board_cash",
    "erase_issuer_primary_label","erase_current_AGM_link","wrong_AGM_cash",
    "remove_issuer_no_transfer_from_board_scope",
])
def test_adversarial_approval_document_mutations_rejected(year,tamper):
    cfg=ALL_YEARS[year]
    if not all((SOURCE_FOLDER/cfg[k+"_filename"]).is_file() for k in ("plan","agm","current")):
        pytest.skip("Issuer originals absent in GitHub checkout")
    vals=[]
    for part in ("plan","agm","current"):
        vals.extend(extract_original_pdf(
            (SOURCE_FOLDER/cfg[part+"_filename"]).read_bytes(),cfg[part+"_sha"]))
    if tamper=="delete_literal_no_transfer":
        vals[1]=vals[1].replace(
            f"（五）{cfg['fiscal']}年度，本公司不实施资本公积金转增股本",
            f"（五）{cfg['fiscal']}年度，本公司拟实施资本公积金转增股本")
    elif tamper=="swap_AGM_approval":
        approved=f"4、议案名称：《{cfg['proposal_title']}》审议结果：通过"
        assert approved in vals[3]
        vals[3]=vals[3].replace(approved,approved.replace("审议结果：通过","审议结果：未通过"),1)
    elif tamper=="erase_board_cash":
        vals[1]=vals[1].replace(f"每10股派发现金红利{cfg['cash_per_ten']}元（含税）",
                              "每10股派发现金红利999元（含税）")
    elif tamper=="erase_issuer_primary_label":
        vals[0]=vals[0].replace("A股代码：600015","A股代码：360020")
    elif tamper=="erase_current_AGM_link":
        vals[5]=vals[5].replace(cfg["approval_prefix"],"未经股东大会审议")
    elif tamper=="wrong_AGM_cash":
        vals[3]=vals[3].replace(f"每10股现金分红{cfg['cash_per_ten']}元（含税）",
                              "每10股现金分红999元（含税）")
    elif tamper=="remove_issuer_no_transfer_from_board_scope":
        vals[1]=vals[1].replace(
            f"（五）{cfg['fiscal']}年度，本公司不实施资本公积金转增股本",
            "（五）另有未批准的资本变动。")
    with pytest.raises(ValueError):
        check_scoped_chain(cfg,*vals)


@pytest.mark.parametrize("year",tuple(ALL_YEARS))
def test_wrong_source_time_or_primary_issuer_rejected(year):
    cfg=ALL_YEARS[year]
    c=copy.deepcopy(cfg)
    c["conservative_plan_usable_day"]="2033-01-01"
    with pytest.raises(ValueError,match="chronology"):
        verify_event_chain(c,fixture_row(cfg),SOURCE_FOLDER)
    c=copy.deepcopy(cfg)
    c["plan_url"]="https://attacker.example/" + cfg["plan_filename"]
    with pytest.raises(ValueError,match="issuer hosted"):
        verify_event_chain(c,fixture_row(cfg),SOURCE_FOLDER)


def test_full_original_source_audit_and_no_reuse_of_outdir(tmp_path):
    if not PARENT_CATALOG.exists() or not SOURCE_FOLDER.exists():
        pytest.skip("Mac-only immutable original sources / parent replay missing")
    src=[
        Path("data/pit/issuer_batch19_20261026/issuer_pdfs"),
        Path("data/pit/issuer_batch30_random_20261026/issuer_pdfs"),
        Path("data/pit/issuer_official_20261026/raw_official_pdfs"),
    ]
    audit=run(PARENT_CATALOG,src,SOURCE_FOLDER,tmp_path/"only_once")
    assert audit["primary_issuer_original_full_sha256_checked"]==89
    assert audit["additional_issuer_hosted_original_full_sha256_checked"]==6
    assert audit["issuer_approved_capital_transfer_zero_newly_resolved"]==2
    assert audit["unresolved_bonus_or_share_rights_before_after"]==[45,45]
    assert audit["other_event_rows_fully_unchanged"]==87
    with pytest.raises(FileExistsError):
        run(PARENT_CATALOG,src,SOURCE_FOLDER,tmp_path/"only_once")


def test_immutable_parent_digest_gate(tmp_path):
    wrong=tmp_path/"modified_parent.json"
    wrong.write_text('{"kind":"unverified"}',encoding="utf-8")
    with pytest.raises(ValueError,match="exact frozen"):
        run(wrong,[],SOURCE_FOLDER,tmp_path/"cannot_be_created")
    assert not (tmp_path/"cannot_be_created").exists()
