"""Issuer-PDF cash/dividend extraction regression tests, no network."""

import pytest

from quant_lab.pit_official_batch import (
    extract_cash_candidates_per_share,
    strict_cash_match, is_issuer_dividend_implementation,
    extract_explicit_pretax_cash_per_share,
)


@pytest.mark.parametrize("text,expected",[
    ("重要内容提示：A股每股现金红利人民币0.41元（含税）", 0.41),
    ("重要内容提示：A股每股现金红利0.073元", .073),
    ("向全体股东每10股派发现金红利1.12元（含税）", .112),
    ("每10股派发现金股利人民币2.280000元（含税）", .228),
    ("A股每股现金红利0.25元，每10股人民币2.5元（含税）", .25),
    ("每１０股派发现金红利２．５元（含税）", .25),
])
def test_pdf_extracts_only_explicit_per_share_or_per_ten_cash(text, expected):
    candidates=extract_cash_candidates_per_share(text)
    assert len(candidates)==1, candidates
    assert candidates[0]==pytest.approx(expected)


def test_thirdparty_agreement_requires_single_pdf_amount():
    assert strict_cash_match([.41], .41)["status"]=="PDF_CASH_MATCHED_TO_THIRDPARTY"
    assert strict_cash_match([.42], .41)["status"]=="PDF_CASH_MISMATCH"
    assert strict_cash_match([.41, .21],.41)["status"]=="PDF_MULTI_AMOUNT_NEEDS_MANUAL_REVIEW"
    assert strict_cash_match([], .41)["cash_per_share_verified"] is None
    assert strict_cash_match([.41], None)["status"]=="OFFICIAL_PDF_NUMBER_ONLY_NOT_RECONCILED"


def test_disclosure_search_rejects_unrelated_announcements():
    assert is_issuer_dividend_implementation("中国葛洲坝集团2020年年度权益分派实施公告")
    assert is_issuer_dividend_implementation("某银行2021年度普通股分红派息实施公告")
    assert not is_issuer_dividend_implementation("筹划重组停牌进展公告")
    assert not is_issuer_dividend_implementation("2022年年度权益分派预案")
    assert not is_issuer_dividend_implementation("终止筹划重大资产重组暨复牌公告")



@pytest.mark.parametrize("text,pretax",[
    ("每股派发现金红利人民币1.50元（含税）",1.5),
    ("每股派发现金股息人民币0.2933元（含税）",.2933),
    ("每10股派30.000000元人民币现金（含税；扣税后每10股派27.000000元）",3.0),
    ("每10股派现金30.23元（含税）",3.023),
    ("每10股派人民币1.48元现金（含税；扣税后每10股派人民币1.332元现金）",.148),
    ("每10股派发现金红利（含税）人民币9.761257元",.9761257),
    ("每10股派发现金股利20元（含税），扣税后18元",2.0),
])
def test_tax_inclusive_gross_cash_overrides_after_tax_value(text,pretax):
    amounts=extract_explicit_pretax_cash_per_share(text)
    assert amounts==pytest.approx([pretax])


def test_after_tax_only_is_never_mislabeled_as_gross():
    assert extract_explicit_pretax_cash_per_share(
        "扣税后每10股派发现金红利18.00元。"
    ) == []
