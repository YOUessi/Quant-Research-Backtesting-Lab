"""EXP020 regression: authenticated primary A-stock first-page identity, no H/CB confusion."""
from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from quant_lab.pit_exp020_issuer_identity_gate import (
    PARENT_SHA256,check_first_page_text,validate_original_header,run
)

TITLE="某某股份有限公司2021年年度权益分派实施公告"
DIVIDEND="某某股份有限公司2021年分红派息实施公告"

@pytest.mark.parametrize("line,symbol,expected", [
    ("证券代码：600000", "SH600000", "SECURITY_CODE"),
    ("股票代码：002202", "SZ002202", "STOCK_CODE"),
    ("A 股股票代码：601336", "SH601336", "EXPLICIT_A_SHARE_STOCK_CODE"),
    ("A股股票代码:601336", "SH601336", "EXPLICIT_A_SHARE_STOCK_CODE"),
])
def test_primary_labeled_a_stock_first_page(line,symbol,expected):
    found=check_first_page_text(line+"\n"+TITLE, symbol)
    assert found["header_type"]==expected
    assert found["primary_a_stock_code"]==symbol[2:]
    assert found["first_page_notice_type"]=="EQUITY_DISTRIBUTION_IMPLEMENTATION"

def test_cash_dividend_notice_not_rejected_as_wrong_title():
    r=check_first_page_text("证券代码：600000\n"+DIVIDEND,"SH600000")
    assert r["first_page_notice_type"]=="CASH_DIVIDEND_IMPLEMENTATION"

def test_ashare_issuer_verified_with_hshare_header_and_other_instruments():
    source=("A 股股票代码：601336\nH 股股票代码：01336\n"
            "优先股代码：360019\n转债代码：113050\n"+TITLE)
    assert check_first_page_text(source,"SH601336")["primary_a_stock_code"]=="601336"

@pytest.mark.parametrize("wrong",[
    "证券代码：600001",
    "股票代码：601336",
    "A 股股票代码：601336",
])
def test_misassigned_primary_stock_is_blocked(wrong):
    with pytest.raises(ValueError,match="disagrees"):
        check_first_page_text(wrong+"\n"+TITLE, "SH600000")

@pytest.mark.parametrize("text",[
    "转债代码：600000\n"+TITLE,
    "优先股代码：600000\n"+TITLE,
    "H 股股票代码：600000\n"+TITLE,
    "正文提及证券代码：600000\n"+TITLE,
    TITLE+"\n证券代码：600000",
    "证券代码： 60000\n"+TITLE,
])
def test_missing_primary_header_rejected(text):
    with pytest.raises(ValueError,match="Missing or ambiguous"):
        check_first_page_text(text,"SH600000")

def test_multiple_labeled_a_stock_headers_rejected_even_same_code():
    text="证券代码：600000\nA 股股票代码：600000\n"+TITLE
    with pytest.raises(ValueError,match="ambiguous"):
        check_first_page_text(text,"SH600000")

@pytest.mark.parametrize("text",[
    "证券代码：600000\n2021年年度权益分派董事会决议",
    "证券代码：600000\n2021年度权益分派预案公告",
    "证券代码：600000\n2021年度债券兑付实施公告",
])
def test_notice_not_current_equity_implementation_rejected(text):
    with pytest.raises(ValueError,match="(title|not identified)"):
        check_first_page_text(text,"SH600000")

@pytest.mark.parametrize("symbol",["600000","US600000","SH60000A","SZ0000011",""])
def test_invalid_exchange_qualified_symbol_fails_closed(symbol):
    with pytest.raises(ValueError,match="exchange-qualified"):
        check_first_page_text("证券代码：600000\n"+TITLE,symbol)

def test_pdf_full_digest_precedes_first_page_interpretation():
    row={"symbol":"SH600000","issuer_original_pdf_sha256":"0"*64}
    with pytest.raises(ValueError,match="full SHA256"):
        validate_original_header(row,b"%PDF original bytes modified")

def test_invalid_pdf_format_not_promoted_even_if_hash_matches():
    raw=b"not actually a PDF"
    row={"symbol":"SH600000","issuer_original_pdf_sha256":hashlib.sha256(raw).hexdigest()}
    with pytest.raises(ValueError,match="Not an original PDF"):
        validate_original_header(row,raw)

def test_wrong_frozen_parent_does_not_create_output(tmp_path:Path):
    bad=tmp_path/"parent.json"
    bad.write_text('{"issuer_events":89}',encoding="utf-8")
    out=tmp_path/"new"
    with pytest.raises(ValueError,match="catalog SHA256"):
        run(bad,[],out)
    assert not out.exists()

def test_prior_audit_output_immutable(tmp_path:Path):
    target=tmp_path/"old"
    target.mkdir()
    with pytest.raises(FileExistsError,match="Never overwrite"):
        run(tmp_path/"no.json",[],target)

def test_parent_sha_is_full_digest():
    assert len(PARENT_SHA256)==64
    assert all(x in "0123456789abcdef" for x in PARENT_SHA256)
