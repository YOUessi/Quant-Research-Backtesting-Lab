"""Official issuer cash option / subscription / ST day source assertions.

These offline tests use representative issuer-clause excerpts only for parser
regression. The real experiment additionally reads the actual PDF bytes and
enforces pinned SHA256, Qlib original index membership and no positive bars.
"""
import pytest

from quant_lab.pit_exp008_original_proofs import _source_proves


def docs():
    return {
        "SH601108_rights":{
            "normalized_text":(
              "财通证券股份有限公司实施配股，2022年3月31日至2022年4月8日为本次配股缴款期，"
              "缴款期公司A股股票及可转换公司债券全天停牌；"
              "2022年4月11日为登记公司网上清算期，公司A股股票继续停牌一天；"
              "2022年4月12日开市起公司A股股票复牌"
            ),"sha256":"a"*64,"url":"https://static.cninfo.com.cn/x",
            "publication_calendar_day":"2022-03-28",
        },
        "SZ002142_rights":{
            "normalized_text":"2021年11月24日（R+1日）至2021年12月1日（R+6日），宁波银行A股股票停止交易",
            "sha256":"b"*64,"url":"https://static.cninfo.com.cn/y",
            "publication_calendar_day":"2021-11-19",
        },
        "SZ002142_result":{
            "normalized_text":"自2021年12月2日开市起，公司A股股票复牌",
            "sha256":"c"*64,"url":"https://static.cninfo.com.cn/z",
            "publication_calendar_day":"2021-12-02",
        },
        "SZ000425_cash_option":{
            "normalized_text":"本公司股票（证券简称徐工机械）将自2022年8月1日开市时起开始停牌，直至现金选择权实施完毕",
            "sha256":"d"*64,"url":"https://static.cninfo.com.cn/k",
            "publication_calendar_day":"2022-07-29",
        },
        "SZ000425_resume":{
            "normalized_text":"公司股票（证券简称徐工机械）自2022年8月17日开市时起复牌",
            "sha256":"e"*64,"url":"https://static.cninfo.com.cn/l",
            "publication_calendar_day":"2022-08-17",
        },
        "SZ002024_risk_warning":{
            "normalized_text":"公司股票交易2022年5月5日开市起停牌一天，并于2022年5月6日开市起复牌；被实施其他风险警示后，公司股票日涨跌幅限制为5%",
            "sha256":"f"*64,"url":"https://static.cninfo.com.cn/m",
            "publication_calendar_day":"2022-04-30",
        },
        "SZ002812_halt":{
            "normalized_text":"公司股票（证券简称恩捷股份）及公司可转换公司债券自2021年6月16日开市起停牌",
            "sha256":"1"*64,"url":"https://static.cninfo.com.cn/n",
            "publication_calendar_day":"2021-06-16",
        },
        "SZ002812_resume":{
            "normalized_text":"公司股票（证券简称恩捷股份）和公司可转换公司债券将于2021年6月23日开市起复牌",
            "sha256":"2"*64,"url":"https://static.cninfo.com.cn/o",
            "publication_calendar_day":"2021-06-23",
        },
    }


@pytest.mark.parametrize("sym,first,ending,sources",[
    ("SH601108","2022-03-31","2022-04-12",("SH601108_rights",)),
    ("SZ002142","2021-11-24","2021-12-02",("SZ002142_rights","SZ002142_result")),
    ("SZ000425","2022-08-01","2022-08-17",("SZ000425_cash_option","SZ000425_resume")),
    ("SZ002024","2022-05-05","2022-05-06",("SZ002024_risk_warning",)),
    ("SZ002812","2021-06-16","2021-06-23",("SZ002812_halt","SZ002812_resume")),
])
def test_exact_original_issuer_halt_and_resumption_words(sym,first,ending,sources):
    rule={"symbol":sym,"first":first,"resume":ending,
          "sources":sources,"category":"TEST_EXACT_ISSUER_STOCK_HALT"}
    actual=_source_proves(rule,docs())
    assert actual["issuer_pdf_exact_full_session_effect_verified"]
    assert not actual["actual_broker_execution_verified"]
    assert actual["first_resumed_exchange_day"]==ending


def test_predicted_duration_without_resume_cannot_pass():
    d=docs()
    d["SZ000425_resume"]["normalized_text"]="现金选择权事件预计停牌10个交易日"
    rule={"symbol":"SZ000425","first":"2022-08-01","resume":"2022-08-17",
          "sources":("SZ000425_cash_option","SZ000425_resume"),
          "category":"TEST"}
    with pytest.raises(ValueError,match="Issuer PDF"):
        _source_proves(rule,d)


def test_convertible_bond_only_resume_not_a_stock_resume():
    d=docs()
    d["SZ002812_resume"]["normalized_text"]="可转换公司债券将于2021年6月23日开市起复牌，公司股票继续停牌"
    rule={"symbol":"SZ002812","first":"2021-06-16","resume":"2021-06-23",
          "sources":("SZ002812_halt","SZ002812_resume"),
          "category":"TEST"}
    with pytest.raises(ValueError,match="Issuer PDF"):
        _source_proves(rule,d)


def test_sz002024_risk_warning_must_have_explicit_effective_band():
    d=docs()
    d["SZ002024_risk_warning"]["normalized_text"]=(
        "公司股票交易2022年5月5日开市起停牌一天，并于2022年5月6日开市起复牌，风险警示")
    rule={"symbol":"SZ002024","first":"2022-05-05","resume":"2022-05-06",
          "sources":("SZ002024_risk_warning",),"category":"TEST"}
    with pytest.raises(ValueError,match="Issuer PDF"):
        _source_proves(rule,d)
