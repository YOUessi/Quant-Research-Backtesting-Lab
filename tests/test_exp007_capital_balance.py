"""Conservative original-issuer company capital reconciliation."""
import pytest
from quant_lab.pit_capital_balance import audit_balanced_issuer_rights


SOURCE="a"*64

def rights(bonus=None,transfer=None):
    return {
        "bonus_ratio_per_nominal_share":bonus,
        "transfer_ratio_per_nominal_share":transfer,
    }


def test_sh600276_hengrui_issuer_total_proves_no_extra_capital_transfer():
    text=(
        "3.分配方案：本次利润分配以方案实施前的公司总股本"
        "5,331,231,328股为基数，向全体股东每股派发现金红利0.2元"
        "（含税），每股派送红股0.2股，共计派发现金红利"
        "1,066,246,265.6元，派送红股1,066,246,266股，"
        "本次分配后总股本为6,397,477,594股。"
    )
    x=audit_balanced_issuer_rights(
        text,rights(bonus=.2),issuer_sha256=SOURCE,
        is_differential_distribution=False,
    )
    assert x["balanced_accounting_inferred_zero_category"]=="transfer"
    assert x["capital_balance_gap_shares"]==pytest.approx(.4)
    assert x["status"].startswith("ISSUER_IN_SAME_PDF")


def test_sh600760_avic_issuer_total_proves_no_extra_bonus():
    text=(
        "3.分配方案：本次利润分配及转增股本以方案实施前的公司"
        "总股本1,400,389,285股为基数，每股派发现金红利"
        "0.24元（含税），以资本公积金向全体股东每股转增0.4股，"
        "共计派发现金红利336,093,428.40元，转增560,155,714股，"
        "本次分配后总股本为1,960,544,999股。"
    )
    x=audit_balanced_issuer_rights(
        text,rights(transfer=.4),issuer_sha256=SOURCE,
        is_differential_distribution=False,
    )
    assert x["balanced_accounting_inferred_zero_category"]=="bonus"
    assert x["pre_nominal_company_shares"]==1400389285
    assert x["post_nominal_company_shares"]==1960544999


def test_sh603392_issuer_share_delivery_against_post_company_total():
    text=(
        "3.分配方案：本次利润分配以方案实施前的公司总股本"
        "433,600,000股为基数，每股派发现金红利0.25元（含税），"
        "每股派送红股0.4股，共计派送红股173,440,000股，"
        "本次分配后总股本为607,040,000股。"
    )
    a=audit_balanced_issuer_rights(
        text,rights(bonus=.4),issuer_sha256=SOURCE,
        is_differential_distribution=False,
    )
    assert a["balanced_accounting_inferred_zero_category"]=="transfer"


def test_same_source_balanced_but_no_issuer_issued_shares_must_hold():
    txt=(
        "本次利润分配以方案实施前的公司总股本100,000,000股为基数，"
        "每股派送红股0.4股，本次分配后总股本为140,000,000股。"
    )
    a=audit_balanced_issuer_rights(
        txt,rights(bonus=.4),issuer_sha256=SOURCE,
        is_differential_distribution=False)
    assert a["status"]=="TOTAL_BALANCE_MATCHES_BUT_ISSUED_SHARES_UNCONFIRMED"
    assert a["balanced_accounting_inferred_zero_category"] is None


def test_differential_distribution_never_allows_inferred_zero():
    txt=(
        "本次利润分配以方案实施前的公司总股本100,000,000股为基数，"
        "每股派送红股0.4股，共计派送红股40,000,000股，"
        "本次分配后总股本为140,000,000股。"
    )
    a=audit_balanced_issuer_rights(
        txt,rights(bonus=.4),issuer_sha256=SOURCE,
        is_differential_distribution=True)
    assert a["status"]=="DIFFERENTIAL_OR_UNDECLARED_ELIGIBILITY_HOLD"


def test_unexplained_new_shares_does_not_resolve_secondary_rights():
    txt=(
        "本次利润分配以方案实施前的公司总股本100,000,000股为基数，"
        "每股派送红股0.4股，共计派送红股40,000,000股，"
        "本次分配后总股本为142,000,000股。"
    )
    a=audit_balanced_issuer_rights(
        txt,rights(bonus=.4),issuer_sha256=SOURCE,
        is_differential_distribution=False)
    assert a["status"]=="CAPITAL_BALANCE_DIFFERENCE_EXCEEDS_ONE_SHARE"


def test_two_distinct_before_after_pairs_are_ambiguous():
    txt=(
        "本次利润分配以方案实施前的公司总股本100,000,000股为基数，"
        "每股派送红股0.4股，共计派送红股40,000,000股，"
        "本次分配后总股本为140,000,000股。"
        "本次利润分配以方案实施前的公司总股本105,000,000股为基数，"
        "每股派送红股0.4股，共计派送红股42,000,000股，"
        "本次分配后总股本为147,000,000股。"
    )
    a=audit_balanced_issuer_rights(
        txt,rights(bonus=.4),issuer_sha256=SOURCE,
        is_differential_distribution=False)
    assert a["balanced_accounting_inferred_zero_category"] is None
    assert len(a["issuer_current_implementation_pre_post_share_pairs"])==2
