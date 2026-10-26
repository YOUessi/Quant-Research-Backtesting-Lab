"""Unambiguous single-security issuer PDF effective halt/resume parsing."""
from quant_lab.pit_halt_source_audit import notice_effects


def test_company_stock_halt_effective_date_from_original_issuer_text():
    t="证券代码：600340，因重大资产事项，公司股票将于2021年1月29日（星期五）开市起停牌。"
    a=notice_effects(t,"SH600340")
    assert a["suspend_start"]=="2021-01-29"
    assert a["resume_start"] is None
    assert a["reason"]=="EXPLICIT_COMPANY_STOCK_DATE"


def test_company_stock_resume_effective_date_from_original_issuer_text():
    t="证券代码：600340，华夏幸福公司股票将于2021年2月19日（星期五）开市起复牌。"
    a=notice_effects(t,"SH600340")
    assert a["resume_start"]=="2021-02-19"
    assert a["suspend_start"] is None


def test_convertible_bond_only_notice_has_no_stock_halt():
    a=notice_effects("证券代码：600340，仅债券将于2021年2月19日开市起停牌。","SH600340")
    assert a["suspend_start"] is None


def test_document_with_both_halt_resume_not_single_date_proof():
    a=notice_effects(
        "证券代码：600340公司股票将于2021年1月29日开市起停牌;"
        "公司股票将于2021年2月19日开市起复牌",
        "SH600340")
    assert a["suspend_start"] is None
    assert a["resume_start"] is None
