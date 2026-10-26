"""New issuer date formats; only full-day stock halts, never bond or estimate."""
from quant_lab.pit_halt_pairs import extract_effects


def test_sse_issuer_halt_effective_from_open_not_expected_duration():
    t=("证券代码600009，经申请，本公司股票自2021年6月10日"
       "（星期四）起停牌，停牌时间不超过10个交易日。")
    r=extract_effects(t,ticker="SH600009")
    assert r["effective_halt_from_open_dates"]==["2021-06-10"]
    assert r["effective_resume_from_open_dates"]==[]


def test_sse_issuer_resume_has_exact_effective_day():
    t=("股票代码600009，根据相关规定，经向上交所申请，"
       "公司股票自2021年6月25日（星期五）开市起复牌。")
    r=extract_effects(t,ticker="SH600009")
    assert r["effective_resume_from_open_dates"]==["2021-06-25"]


def test_szse_halt_and_resume_stocks_not_just_a_transfer_bond():
    t=("证券代码002352经公司向交易所申请，公司股票"
       "（证券简称：顺丰控股，证券代码：002352）"
       "自2021年2月5日（星期五）开市起停牌。")
    r=extract_effects(t,ticker="SZ002352")
    assert r["effective_halt_from_open_dates"]==["2021-02-05"]
    t=("证券代码002352公司股票（股票简称：顺丰控股）"
       "自2021年2月10日（星期三）上午开市起复牌。")
    r=extract_effects(t,ticker="SZ002352")
    assert r["effective_resume_from_open_dates"]==["2021-02-10"]


def test_company_bond_only_pause_must_not_be_a_stock_halt():
    t=("证券代码600009公司可转换公司债券自2021年6月10日"
       "（星期四）开市起停牌。公司股票正常交易。")
    r=extract_effects(t,ticker="SH600009")
    assert r["effective_halt_from_open_dates"]==[]


def test_issuer_effective_resume_afternoon_is_not_full_session():
    t=("证券代码000063，经向深圳证券交易所申请，"
       "公司股票将于2022年3月23日下午开市起复牌。")
    r=extract_effects(t,ticker="SZ000063")
    assert r["has_intraday_only_resumption"]


def test_announcement_only_predicted_duration_does_not_infer_resume():
    t=("股票代码600009本公司股票自2021年6月10日起停牌，"
       "预计停牌时间不超过10个交易日。")
    r=extract_effects(t,ticker="SH600009")
    assert r["effective_resume_from_open_dates"]==[]
