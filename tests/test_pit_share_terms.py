"""Original issuer cash-only plan requires both explicit negative clauses."""
from quant_lab.pit_share_terms import zero_stock_bonus_sentence


def test_positive_no_bonus_clause_is_sufficient_only_with_both_statements():
    t="本次分配方案：每10股派发现金红利2.28元（含税），不送红股，不以公积金转增股本。"
    assert zero_stock_bonus_sentence(t)
    assert zero_stock_bonus_sentence("每10股派1元，不送红股，也不以资本公积金转增股本")
    assert zero_stock_bonus_sentence("不送红股，不进行资本公积金转增股本")


def test_no_cash_only_inference_from_silence_or_bonus_mention():
    assert not zero_stock_bonus_sentence("每10股派2元，原始股本10亿股。")
    assert not zero_stock_bonus_sentence("本次不送红股，后续还可能有转增计划")
    assert not zero_stock_bonus_sentence("10送3转2，派发现金红利1元")
