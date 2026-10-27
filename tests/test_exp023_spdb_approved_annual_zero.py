"""EXP023: annual explicit dash + actual approved AGM + final cash chain.

All unit tests are pure strings/immutable dictionaries; no downloaded primary
PDF needs to be committed to GitHub or available in CI. The EXP023 offline
empirical run separately validates whole-file original SHA256 for 10 PDF
sources and all 89 archived original issuer implementation documents.
"""
from copy import deepcopy

import pytest

from quant_lab.pit_exp023_spdb_approved_annual_zero import (
    SOURCES, GRADE, apply_cash_only_original_proof,
    check_exact_annual_bonus_transfer_table,
    verify_five_original_issuer_documents,
)


def source_docs(fiscal="2020"):
    cfg=SOURCES[fiscal]
    fy=cfg["fiscal"]
    money=cfg["cash_per_ten"]
    per=cfg["cash_per_share"]
    agm_money="4.8" if fy=="2020" else "4.1"
    r,x=[int(w) for w in cfg["record"].split("-")], [
        int(w) for w in cfg["ex"].split("-")
    ]
    date=f"{r[0]}/{r[1]}/{r[2]}"
    ex=f"{x[0]}/{x[1]}/{x[2]}"
    annual={
        "first": "",
        "selected": (
            "5.1.2公司近三年的普通股股利分配方案或预案、资本公积转增股本方案或预案"
            "分红年度每10股送红股数（股）每10股派息数（元）（含税）"
            "每10股转增数（股）现金分红的数额（含税）"
            f"{fy}年-{money}-14,00059,00025.00"
            f"注：{fy}年度利润分配预案尚需股东大会审议批准后方可实施"
            f"5.1.3公司{fy}年度利润分配预案"
        ),
    }
    board={
        "first": (
            f"证券代码：600000上海浦东发展银行股份有限公司"
            f"{fy}年度利润分配方案公告"
        ),
        "selected": (
            f"证券代码：600000上海浦东发展银行股份有限公司{fy}年度利润分配方案公告"
            f"每股派发现金股利人民币{per}元（含税）"
            f"本次利润分配方案尚待公司{fy}年年度股东大会审议通过后方可实施"
        ),
    }
    materials={
        "first": (
            f"上海浦东发展银行股份有限公司{fy}年年度股东大会会议资料"
        ),
        "selected": (
            f"议案四：上海浦东发展银行股份有限公司{fy}年度利润分配的预案"
            f"各位股东：向全体股东每10股派送现金股利{agm_money}元人民币（含税）。"
        ),
    }
    resolution={
        "first": (
            f"证券代码：600000上海浦东发展银行股份有限公司{fy}年年度股东大会决议公告"
        ),
        "selected": (
            f"4、议案名称：公司{fy}年度利润分配的预案审议结果：通过"
            f"公司{fy}年度利润分配方案如下："
            f"以实际总股本为基数，向全体股东每10股派发现金股利人民币{money}元（含税）。"
            "5、议案名称：关于其他事项的决议"
        ),
    }
    final={
        "first": (
            f"证券代码：600000上海浦东发展银行股份有限公司"
            f"{fy}年度普通股分红派息实施公告"
        ),
        "selected": (
            f"证券代码：600000上海浦东发展银行股份有限公司{fy}年度普通股分红派息实施公告"
            f"A股每股现金红利人民币{per}元（含税）"
            f"A股{date}－{ex}{ex}"
            "差异化分红送转：否"
            f"本次利润分配方案经公司{cfg['agm_held']}召开的{fy}年年度股东大会审议通过"
            f"本次利润分配以方案实施前的公司总股本"
            f"{int(cfg['distribution_base']):,}股为基数，"
            f"每股派发现金红利人民币{per}元（含税），"
            f"共计派发现金红利人民币{float(cfg['expected_gross_distributed_cash']):,.2f}元（含税）"
        ),
    }
    return {
        "annual":annual, "board":board,"agm_materials":materials,
        "agm_resolution":resolution,"implementation":final
    }


@pytest.mark.parametrize("fiscal", ["2020","2021"])
def test_exact_fiscal_approved_matrix_cash_only_from_all_five_documents(fiscal):
    outcome=verify_five_original_issuer_documents(
        SOURCES[fiscal],source_docs(fiscal)
    )
    assert outcome["proposal_bonus_per_10"]=="0_AS_SOURCE_DASH"
    assert outcome["proposal_capital_transfer_per_10"]=="0_AS_SOURCE_DASH"
    assert outcome["agm_resolution_approved_same_fiscal_cash_scheme"]
    assert outcome["final_issuer_current_approved_annual_cash_matched"]
    assert outcome["zero_bonus_and_transfer_source_grade"]==GRADE
    assert not outcome["complete_corporate_actions_amendment_history_verified"]
    assert not outcome["individual_broker_new_shares_or_cash_credited"]


@pytest.mark.parametrize("year",["2020","2021"])
def test_annual_dash_semantics_rejected_when_mislabelled_or_cash_modified(year):
    source=source_docs(year)
    cfg=SOURCES[year]
    good=source["annual"]["selected"]
    # Cash-only is asserted from TWO named numeric source columns.
    for bad in (
        good.replace("每10股送红股数（股）","每10股送红股比例"),
        good.replace("每10股转增数（股）","每10股股份总额"),
        good.replace(f"{year}年-{cfg['cash_per_ten']}-",
                     f"{year}年2{cfg['cash_per_ten']}-"),
        good.replace(f"{year}年-{cfg['cash_per_ten']}-",
                     f"{year}年-{cfg['cash_per_ten']}2"),
        good.replace(cfg["cash_per_ten"],"6.66"),
        good.replace("尚需股东大会审议批准后方可实施","已完成自动生效"),
    ):
        with pytest.raises(ValueError,match="Annual|proposal"):
            check_exact_annual_bonus_transfer_table(bad,cfg)


@pytest.mark.parametrize("year",["2020","2021"])
def test_no_unapproved_board_or_unmatched_AGM_motion_falls_through(year):
    good=source_docs(year)
    cases=[
        ("board","尚待公司","不需公司"),
        ("agm_materials","议案四：","议案八："),
        ("agm_resolution","审议结果：通过","审议结果：未通过"),
        ("agm_resolution","证券代码：600000","证券代码：600015"),
        ("implementation","证券代码：600000","证券代码：110059"),
        ("implementation","差异化分红送转：否","差异化分红送转：是"),
        ("implementation","共计派发现金红利人民币","共计转增股本人民币"),
    ]
    for part,a,b in cases:
        source=deepcopy(good)
        if a in source[part]["first"]:
            source[part]["first"]=source[part]["first"].replace(a,b)
        source[part]["selected"]=source[part]["selected"].replace(a,b)
        with pytest.raises(ValueError):
            verify_five_original_issuer_documents(SOURCES[year],source)


def old_unverified_row():
    return {
        "event_id":"add4bd8b25db659099f2af93",
        "symbol":"SH600000","ex_date":"2021-07-21",
        "announcement_day":"2021-07-13",
        "earliest_usable_exchange_day":"2021-07-14",
        "record_date":"2021-07-20",
        "scheduled_cash_payment_day":"2021-07-21",
        "gross_cash_per_old_nominal_share":.48,
        "issuer_original_pdf_sha256":"fbadb95f0d82ebe980c559cb5bf5b8d4489b2b1e9374f585704a3719c79916ba",
        "issuer_original_pdf_url":"https://static.cninfo.com.cn/finalpage/2021-07-13/1210467899.PDF",
        "bonus_shares_per_old_share":None,
        "capital_transfer_shares_per_old_share":None,
        "full_new_nominal_share_multiplier":None,
        "complete_rights_supported_by_issuer_original":False,
        "rights_evidence":{"bonus":"BONUS_UNCONFIRMED","transfer":"TRANSFER_UNCONFIRMED"},
        "cash_rights_nominal_not_qlib_adjusted":True,
        "broker_share_delivery_and_cash_payment_verified":False,
        "original_publication_intraday_time_certified":False,
        "historical_factor_vintage_available":False,
    }


def fake_final_proof():
    r=old_unverified_row()
    return {
        "event_id":r["event_id"],
        "symbol":r["symbol"],
        "ex_date":r["ex_date"],
        "proof_grade":GRADE,
        "issuer_proposal_approved_zero_bonus":"0",
        "issuer_proposal_approved_zero_capital_transfer":"0",
    }


def test_only_verified_two_rights_fields_change_other_economics_are_frozen():
    original=old_unverified_row()
    output=apply_cash_only_original_proof(original,fake_final_proof())
    assert output["bonus_shares_per_old_share"]==0.
    assert output["capital_transfer_shares_per_old_share"]==0.
    assert output["full_new_nominal_share_multiplier"]==1.
    assert output["complete_rights_supported_by_issuer_original"]
    assert output["gross_cash_per_old_nominal_share"]==original["gross_cash_per_old_nominal_share"]
    assert output["earliest_usable_exchange_day"]==original["earliest_usable_exchange_day"]
    assert output["broker_share_delivery_and_cash_payment_verified"] is False
    assert output["historical_factor_vintage_available"] is False
    assert original["bonus_shares_per_old_share"] is None
    assert original["capital_transfer_shares_per_old_share"] is None


@pytest.mark.parametrize("case",["wrong_event","wrong_grade","negative_share","already_verified"])
def test_no_forged_or_duplicate_rights_upgrade(case):
    row=old_unverified_row()
    proof=fake_final_proof()
    if case=="wrong_event":
        proof["event_id"]="attacker"
    elif case=="wrong_grade":
        proof["proof_grade"]="UNVERIFIED_BROKER_DATA"
    elif case=="negative_share":
        proof["issuer_proposal_approved_zero_capital_transfer"]="-1"
    elif case=="already_verified":
        row["bonus_shares_per_old_share"]=0
    with pytest.raises(ValueError,match="Unproven"):
        apply_cash_only_original_proof(row,proof)
