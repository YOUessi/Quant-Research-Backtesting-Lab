"""Offline historical PDF and primary exchange/broker evidence tests.

Fixtures mimic visible ORIGINAL fund/table column content, not numeric
results synthesized for the empirical study. Full reproducibility CLI
checks the original downloaded PDFs' SHA256, pages, exchange calendar,
frozen 139 missing member-day keys and official dated source bytes.
"""
from copy import deepcopy
from pathlib import Path
import hashlib

import pytest

from quant_lab.pit_fund_suspension_evidence import (
    SOURCES, verify_exchange_original, verify_broker_original,
    verify_fund_text, sha256_file,
)


def fund_text(key):
    expected=SOURCES[key]
    y,m,d=expected["publication_day"].split("-")
    cover=(
        expected["name"]+"2021 年中期报告 2021 年 6 月 30 日"
        +" 基金管理人："+expected["manager"]
        +f" 送出日期：{int(y)}年{int(m)}月{int(d)}日"
    )
    shares=f"{expected['reported_shares']:,}"
    val=f"{expected['reported_stock_mark']:,.2f}"
    reason="重大事项停牌" if key=="fund1" else "临时停牌"
    table=(
        "6.4.12.2 期末持有的暂时停牌等流通受限股票"
        "股票代码 股票名称 停牌日期 停牌原因 期末估值单价"
        "复牌日期 复牌开盘单价 数量（股） 期末成本总额 期末估值总额"
        f" 002024 苏宁易购 2021年6月16日 {reason} "
        f"5.59 2021年7月6日 6.15 {shares} 2021.05 {val}"
    )
    return cover,table


@pytest.mark.parametrize("name",["fund1","fund2"])
def test_independent_periodic_reports_are_retrospective_not_decision_day(name):
    first,table=fund_text(name)
    value=verify_fund_text(first,table,expected=SOURCES[name])
    assert value["historical_halt_start_reported"]=="2021-06-16"
    assert value["eventual_actual_resume_reported"]=="2021-07-06"
    assert value["halted_share_mark_at_2021_06_30"]==pytest.approx(5.59)
    assert value["reported_resumption_open"]==pytest.approx(6.15)
    assert value["retrospectively_reported_after_resume"]
    assert value["not_historical_decision_day_observable"]


def test_source_pdf_different_values_rejected():
    first,table=fund_text("fund1")
    for corrupted in [table.replace("6.15","6.45"),
                      table.replace("5.59","5.95"),
                      table.replace("2021年7月6日","2021年7月7日"),
                      table.replace("10,623,856.49","10,623,856.48")]:
        with pytest.raises(ValueError,match="Original fund table"):
            verify_fund_text(first,corrupted,expected=SOURCES["fund1"])


def test_fund_cover_and_publisher_time_mismatch_rejected():
    first,table=fund_text("fund2")
    with pytest.raises(ValueError,match="cover/manager/publication"):
        verify_fund_text(
            first.replace("2021年8月31日","2021年6月30日"),
            table,expected=SOURCES["fund2"]
        )
    with pytest.raises(ValueError,match="cover/manager/publication"):
        verify_fund_text(
            first.replace("中科沃土基金管理有限公司","融通基金管理有限公司"),
            table,expected=SOURCES["fund2"]
        )


def test_primary_exchange_only_establishes_open_start_not_resume():
    fixture=(
        "<html><body><h2>关于苏宁易购集团股份有限公司股票临时停牌的公告</h2>"
        "<p>时间：2021-06-16</p><p>证券代码：002024</p>"
        "<p>苏宁易购公司股票于2021年6月16日开市起临时停牌，"
        "待公司通过指定媒体披露相关公告后复牌。</p>"
        "<p>深圳证券交易所</p></body></html>"
    )
    result=verify_exchange_original(fixture)
    assert result["initial_full_session_halt_from"]=="2021-06-16"
    assert result["resume_effective_date_given"] is None
    with pytest.raises(ValueError,match="initial halt"):
        verify_exchange_original(fixture.replace("2021年6月16日开市","2021年6月17日开市"))


def test_broker_row_blank_resume_kept_unknown():
    page=(
        "<html><body><h1>标的证券信息提示(2021-6-30)</h1>"
        "<table><tr><th>序号</th><th>证券代码</th><th>证券简称</th>"
        "<th>停牌开始时间</th><th>复牌时间</th><th>停牌原因</th></tr>"
        "<tr><td>5</td><td>002024.sz</td><td>苏宁易购</td>"
        "<td>2021-06-16 09:30:00</td><td></td><td>临时停牌</td></tr>"
        "</table></body></html>"
    )
    result=verify_broker_original(page)
    assert result["resume_time"] is None
    assert result["does_not_establish_actual_resume_day"]
    with pytest.raises(ValueError,match="fields disagree"):
        verify_broker_original(page.replace("<td></td>", "<td>2021-07-06</td>"))


def test_hash_check_does_not_accept_changed_remote_document(tmp_path:Path):
    file=tmp_path/"fund_original.pdf"
    file.write_bytes(b"%PDF-original")
    expected=hashlib.sha256(file.read_bytes()).hexdigest()
    assert sha256_file(file,expected)==expected
    file.write_bytes(b"%PDF-revised")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        sha256_file(file,expected)
