"""Independent OHLCV presence audit never infers verified fill or official halt."""
from quant_lab.pit_market_gap_crosscheck import classify_missing


def test_trade_presence_mismatch_is_flagged_not_backfilled():
    o=classify_missing(
        {"2021-01-29","2021-02-01","2021-02-02"},
        {"2021-02-01","2021-02-19"},
    )
    assert o["cross_source_presence_discrepancies"]==1
    assert o["qlib_missing_eastmoney_positive_daily_bar"]==["2021-02-01"]
    assert o["both_daily_sources_absent_not_official_halt_certificate"]==2
    assert o["auction_order_fill_certified"] is False


def test_complete_independent_gap_does_not_certify_suspension():
    a=classify_missing({"2021-01-29"},set())
    assert a["both_daily_sources_absent_not_official_halt_certificate"]==1
    assert a["qlib_missing_eastmoney_positive_daily_bar"]==[]
    assert a["auction_order_fill_certified"] is False
