"""SSE original issuer implementation PDFs: per-share bonus/transfer forms."""
import pytest
from quant_lab.pit_share_distribution import extract_share_terms


def test_hengrui_2021_original_sse_each_share_02_bonus_not_cash_only():
    text=(
      "本次利润分配以方案实施前的公司总股本为基数，"
      "向全体股东每股派发现金红利0.2元（含税），"
      "每股派送红股0.2股，共计派送红股1,066,246,266股。"
    )
    r=extract_share_terms(text)
    assert r["bonus_per_ten_distinct_candidates"]==[2.0]
    assert r["bonus_ratio_per_nominal_share"]==pytest.approx(.2)
    assert r["transfer_ratio_per_nominal_share"] is None
    assert r["known_positive_stock_rights"] is True
    assert r["known_complete"] is False  # transfer explicitly zero is unproven


def test_avic_2021_each_share_04_capital_transfer_not_cash_only():
    text=(
      "本次利润分配及转增股本以方案实施前的公司总股本为基数，"
      "每股派发现金红利0.24元（含税），"
      "以资本公积金向全体股东每股转增0.4股，"
      "本次分配后总股本为1,960,544,999股。"
    )
    r=extract_share_terms(text)
    assert r["transfer_per_ten_distinct_candidates"]==[4.0]
    assert r["transfer_ratio_per_nominal_share"]==pytest.approx(.4)
    assert r["bonus_ratio_per_nominal_share"] is None
    assert r["known_complete"] is False


def test_sse_each_share_and_each_ten_consistent_deduplicate():
    t="每股派送红股0.2股，每10股派送2股，每股转增0.3股，每10股转增3股"
    r=extract_share_terms(t)
    assert r["bonus_per_ten_distinct_candidates"]==[2.0]
    assert r["transfer_per_ten_distinct_candidates"]==[3.0]
    assert r["full_nominal_share_multiplier_issuer_verified"]==pytest.approx(1.5)


def test_sse_divergent_in_same_original_pdf_goes_to_hold():
    r=extract_share_terms("每股派送红股0.2股，调整后每10股派送3股")
    assert r["bonus_ratio_per_nominal_share"] is None
    assert "CONFLICTING" in r["bonus_source_status"]


def test_generic_issuer_broker_boilerplate_does_not_create_shares():
    r=extract_share_terms(
      "派送红股或转增股本的，由中国结算上海分公司根据股权登记日上海"
      "证券交易所收市后登记在册股东持股数直接计入股东账户。"
    )
    assert r["bonus_ratio_per_nominal_share"] is None
    assert r["transfer_ratio_per_nominal_share"] is None
