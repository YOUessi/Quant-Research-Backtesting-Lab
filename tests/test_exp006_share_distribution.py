"""Original issuer bonus/transfer shares: conflict/unknown handling."""
import pytest

from quant_lab.pit_share_distribution import extract_share_terms


def test_positive_transfer_and_cash_bonus_are_distinct():
    t=("本次实施的利润分配及资本公积金转增股本方案：向股东"
       "每10股派发现金红利15元（含税），不送红股，"
       "同时以资本公积金向全体股东每10股转增6股。")
    out=extract_share_terms(t)
    assert out["bonus_ratio_per_nominal_share"]==0.0
    assert out["transfer_ratio_per_nominal_share"]==pytest.approx(.6)
    assert out["full_nominal_share_multiplier_issuer_verified"]==pytest.approx(1.6)
    assert out["known_complete"]


def test_2021_transfer_plan_without_bonus_disclosure_is_partial():
    r=extract_share_terms(
        "每10股派发现金红利15元含税，每10股转增8股不变"
    )
    assert r["transfer_ratio_per_nominal_share"]==pytest.approx(.8)
    assert r["bonus_ratio_per_nominal_share"] is None
    assert not r["known_complete"]


def test_cash_only_explicit_negative_transfer_and_bonus():
    r=extract_share_terms(
        "每10股派发现金股利2.28元（含税），不送红股，不以公积金转增股本。"
    )
    assert r["known_complete"]
    assert r["full_nominal_share_multiplier_issuer_verified"]==1.0


def test_nothing_written_means_unknown_not_zero():
    r=extract_share_terms("仅派发现金股利，每10股派人民币1.0元现金")
    assert not r["known_complete"]
    assert r["bonus_ratio_per_nominal_share"] is None
    assert r["transfer_ratio_per_nominal_share"] is None


def test_ambiguous_old_and_new_transfer_causes_hold():
    r=extract_share_terms(
        "原方案每10股转增5股，修正后每10股转增6股"
    )
    assert r["transfer_ratio_per_nominal_share"] is None
    assert "CONFLICTING" in r["transfer_source_status"]


def test_positive_and_negative_mixed_in_same_issuer_pdf_not_resolved():
    r=extract_share_terms("不以公积金转增股本，另每10股转增8股")
    assert r["transfer_ratio_per_nominal_share"] is None
    assert not r["known_complete"]


def test_issuer_10_bonus_2_and_capital_transfer_3():
    r=extract_share_terms("每10股送2股，每10股转增3股")
    assert r["bonus_ratio_per_nominal_share"]==pytest.approx(.2)
    assert r["transfer_ratio_per_nominal_share"]==pytest.approx(.3)
    assert r["full_nominal_share_multiplier_issuer_verified"]==pytest.approx(1.5)
