"""EXP021 safety boundaries; full primary bytes are separately replayed on Mac."""
import copy
from pathlib import Path

import pytest

from quant_lab.pit_exp021_cross_notice_bonus import (
    BASE_SHA256, QUARTERLY_SHA, IMPLEMENTATION_SHA, GRADE,
    check_plan_link, verify_two_sources, apply_proof, run,
)

def source_sections():
    qhead = "苏州迈为科技股份有限公司2021年第一季度报告2021-041"
    q = (
        "2020年度利润分配事项公司于2021年4月9日召开第二届董事会第十三次会议"
        "以公司截至2021年3月31日总股本57,277,225股为基数"
        "每10股派发现金红利15元（含税）"
        "不送红股；同时以资本公积金向全体股东每10股转增8股"
        "合计转增45,821,780股转增后公司总股本为103,099,005股"
        "截至本报告公告日上述议案尚需经过2020年年度股东大会审议通过"
        "重要事项概述"
    )
    ihead = (
        "证券代码：300751证券简称：迈为股份公告编号：2021-045"
        "苏州迈为科技股份有限公司2020年年度权益分派实施公告"
    )
    i = (
        "一、股东大会审议通过利润分配及资本公积金转增股本方案的情况"
        "2021年4月30日获2020年年度股东大会审议通过"
        "2021年4月10日公告编号：2021-030"
        "股本由57,277,225股增加至57,278,725股"
        "送红股比例、资本公积金转增股本比例固定不变"
        "每10股派发现金红利15元（含税）不变"
        "每10股转增8股不变"
        "本次实施的分配方案与股东大会审议通过的分配方案一致"
        "二、本次实施的利润分配及资本公积金转增股本方案"
        "以公司现有总股本57,278,725股为基数"
        "每10股派15.000000元人民币现金"
        "以资本公积金向全体股东每10股转增8股"
        "分红前本公司总股本为57,278,725股"
        "分红后总股本增至103,101,705股"
        "三、权益分派日期"
    )
    return qhead,q,ihead,i

def existing_row():
    return {
        "symbol":"SZ300751","event_id":"4172b0cd291fcc8ead62d3fa",
        "ex_date":"2021-05-18","announcement_day":"2021-05-10",
        "earliest_usable_exchange_day":"2021-05-11",
        "record_date":"2021-05-17","scheduled_cash_payment_day":None,
        "gross_cash_per_old_nominal_share":1.5,
        "issuer_original_pdf_sha256":IMPLEMENTATION_SHA,
        "issuer_original_pdf_url":"https://static.cninfo.com.cn/finalpage/2021-05-10/1209949702.PDF",
        "bonus_shares_per_old_share":None,
        "capital_transfer_shares_per_old_share":.8,
        "full_new_nominal_share_multiplier":None,
        "complete_rights_supported_by_issuer_original":False,
        "rights_evidence":{"bonus":"BONUS_UNCONFIRMED","transfer":"EXPLICIT_ISSUER_PER_TEN_TRANSFER"},
        "cash_rights_nominal_not_qlib_adjusted":True,
        "broker_share_delivery_and_cash_payment_verified":False,
        "historical_factor_vintage_available":False,
        "original_publication_intraday_time_certified":False,
    }

def proof():
    return {
        "event_id":"4172b0cd291fcc8ead62d3fa",
        "source_grade":GRADE,
        "quarterly_source_pdf_full_sha256":QUARTERLY_SHA,
        "final_implementation_pdf_full_sha256":IMPLEMENTATION_SHA,
        "prior_fiscal_plan_no_bonus_explicit":True,
        "bonus_per_old_share":"0","nominal_multiplier":"1.8",
        "implementation_shares_before":57278725,
        "implementation_shares_after":103101705,
    }

def test_valid_continuity_no_bonus_but_positive_transfer():
    got=check_plan_link(*source_sections())
    assert got["bonus_per_old_share"]=="0"
    assert got["plan_transfer_per_old_share"]=="0.8"
    assert got["nominal_multiplier"]=="1.8"
    assert got["intervening_exercise_share_increase"]==1500
    assert got["current_transfer_shares"]==45822980
    assert got["implementation_shares_after"]==103101705

@pytest.mark.parametrize("part,old,new", [
    (0,"2021-041","2022-041"),
    (0,"苏州迈为科技股份有限公司","不同公司股份有限公司"),
    (1,"2020年度利润分配事项","2019年度利润分配事项"),
    (1,"不送红股","送红股"),
    (1,"每10股转增8股","每10股转增6股"),
    (1,"45,821,780股","45,821,781股"),
    (1,"103,099,005股","103,099,006股"),
    (1,"尚需经过2020年年度股东大会审议通过","已完成全部实际入账"),
    (2,"证券代码：300751","证券代码：300752"),
    (2,"2020年年度权益分派实施公告","2021年年度权益分派实施公告"),
    (3,"2021年4月30日","2021年5月30日"),
    (3,"2021-030","2021-031"),
    (3,"股本由57,277,225股增加至57,278,725股","股本由57,277,225股增加至57,279,725股"),
    (3,"送红股比例、资本公积金转增股本比例固定不变","送红股比例发生变化"),
    (3,"本次实施的分配方案与股东大会审议通过的分配方案一致",
        "本次实施的分配方案与股东大会审议通过的分配方案不一致"),
    (3,"每10股转增8股不变","每10股转增6股不变"),
    (3,"每10股派15.000000元人民币现金","每10股派16.000000元人民币现金"),
    (3,"分红后总股本增至103,101,705股","分红后总股本增至103,101,706股"),
    (3,"三、权益分派日期","三、计划变更"),
])
def test_reject_mutated_original_evidence_clause(part,old,new):
    fields=list(source_sections())
    assert old in fields[part]
    fields[part]=fields[part].replace(old,new)
    with pytest.raises(ValueError):
        check_plan_link(*fields)

def test_only_bonus_is_upgraded_and_old_approved_transfer_not_changed():
    row=existing_row()
    original=copy.deepcopy(row)
    result=apply_proof(row,proof())
    assert row==original
    assert result["bonus_shares_per_old_share"]==0.0
    assert result["capital_transfer_shares_per_old_share"]==0.8
    assert result["full_new_nominal_share_multiplier"]==1.8
    assert result["complete_rights_supported_by_issuer_original"] is True
    assert result["rights_evidence"]["transfer"]==original["rights_evidence"]["transfer"]
    assert result["rights_evidence"]["bonus"]==GRADE
    assert result["exp021_cross_issuer_original_notice_proof"]==proof()
    assert result["scheduled_cash_payment_day"] is None
    for name in ("record_date","ex_date","announcement_day",
                 "earliest_usable_exchange_day","gross_cash_per_old_nominal_share",
                 "broker_share_delivery_and_cash_payment_verified",
                 "historical_factor_vintage_available",
                 "original_publication_intraday_time_certified"):
        assert result[name]==original[name]

@pytest.mark.parametrize("which,value", [
    ("event_id","wrong"),("source_grade","guess"),
    ("quarterly_source_pdf_full_sha256","f"*64),
    ("final_implementation_pdf_full_sha256","f"*64),
    ("prior_fiscal_plan_no_bonus_explicit",False),
    ("bonus_per_old_share","0.1"),
    ("nominal_multiplier","1.0"),
    ("implementation_shares_before",57277225),
    ("implementation_shares_after",103101704),
])
def test_forged_documented_proof_refused(which,value):
    altered=proof()
    altered[which]=value
    with pytest.raises(ValueError):
        apply_proof(existing_row(),altered)

@pytest.mark.parametrize("which,value", [
    ("bonus_shares_per_old_share",0.0),
    ("capital_transfer_shares_per_old_share",0.7),
    ("complete_rights_supported_by_issuer_original",True),
    ("event_id","wrong"),
])
def test_overwrite_or_identity_conflict_refused(which,value):
    row=existing_row()
    row[which]=value
    with pytest.raises(ValueError):
        apply_proof(row,proof())

def test_wrong_pdf_bytes_are_rejected_prior_to_parsing():
    with pytest.raises(ValueError,match="SHA256"):
        verify_two_sources(existing_row(),b"%PDF-1.7\nfake",b"%PDF-1.7\nfake")

def test_wrong_parent_catalog_does_not_write(tmp_path):
    fake=tmp_path/"parent.json"
    fake.write_text('{"kind":"test"}')
    out=tmp_path/"new"
    with pytest.raises(ValueError,match="SHA256"):
        run(fake,[],tmp_path/"unprovided.pdf",out)
    assert not out.exists()

def test_prior_evidence_destination_never_overwritten(tmp_path):
    existing=tmp_path/"existing"
    existing.mkdir()
    (existing/"original").write_text("immutable")
    with pytest.raises(FileExistsError):
        run(tmp_path/"missing.json",[],tmp_path/"missing.pdf",existing)
    assert (existing/"original").read_text()=="immutable"

def test_full_sha_and_source_version_are_hard_pins():
    assert len(BASE_SHA256)==len(QUARTERLY_SHA)==len(IMPLEMENTATION_SHA)==64
    assert QUARTERLY_SHA!=IMPLEMENTATION_SHA
