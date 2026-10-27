"""EXP019 regression: publication-to-implementation stability is negative, not zero-share proof."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from quant_lab.pit_exp019_unresolved_rights_negative import (
    PARENT_SHA256, classify_unresolved_text, run, source_inventory,
)


@pytest.mark.parametrize("source", [
    "2、自分配方案披露至实施期间，公司总股本未发生变化。",
    "自本次权益分派方案披露至实施期间，公司股本总额未发生变化。",
    "自2020年度权益分派方案披露至实施期间，公司股本总额未发生变化。",
    "本次分配方案披露至实施期间公司总股本未发生变化。",
    "自权益分派方案披露至实施期间公司股本总额未发生变化。",
    "自本次分配方案披露至本公告日，公司股本总额未发生变化。",
])
def test_lookback_stability_is_never_current_stock_rights_proof(source):
    result = classify_unresolved_text(source)
    assert result["negative_evidence_class"] == (
        "PRE_IMPLEMENTATION_STABILITY_IS_NOT_POST_DISTRIBUTION_PROOF")
    assert len(result["pre_implementation_stability_snippets"]) == 1
    assert result["zero_bonus_certified_by_this_audit"] is False
    assert result["zero_transfer_certified_by_this_audit"] is False
    assert result["current_rights_issuance_certified"] is False


@pytest.mark.parametrize("source", [
    "",
    "不送红股亦不以资本公积金转增股本。",
    "上市公司曾经没有发生股本变动。",
    "本次分红每10股派发现金3元，股权登记日为2022年7月1日。",
])
def test_other_source_text_never_auto_upgrades_rights(source):
    result = classify_unresolved_text(source)
    assert result["negative_evidence_class"] == "UNRESOLVED_NO_SOURCE_GRADE_UPGRADE"
    assert result["pre_implementation_stability_snippets"] == []
    assert result["zero_bonus_certified_by_this_audit"] is False
    assert result["zero_transfer_certified_by_this_audit"] is False


def test_post_distribution_capital_phrase_still_requires_separate_source_review():
    result = classify_unresolved_text("本次权益分派实施后，公司总股本保持不变。")
    assert result["current_change_phrase_requires_separate_plan_review"] is True
    assert result["current_rights_issuance_certified"] is False
    assert result["zero_bonus_certified_by_this_audit"] is False


def test_historical_clause_is_not_overridden_by_current_boilerplate():
    text = ("自分配方案披露至实施期间公司总股本未发生变化。"
            "未来实施分红时须按约定调整。")
    result = classify_unresolved_text(text)
    assert result["negative_evidence_class"].startswith("PRE_IMPLEMENTATION")
    assert not result["zero_transfer_certified_by_this_audit"]


def test_frozen_parent_digest_is_complete_sha256():
    assert len(PARENT_SHA256) == 64
    assert all(c in "0123456789abcdef" for c in PARENT_SHA256)


def test_missing_original_archive_is_not_treated_as_empty(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="archive"):
        source_inventory([], [tmp_path / "absent"])


def test_mismatched_source_digest_fail_closed(tmp_path: Path):
    bad = tmp_path / "s.pdf"
    bad.write_bytes(b"%PDF-1.7 bogus original")
    row = {
        "event_id": "fixture", "issuer_original_pdf_sha256": "0" * 64,
        "announcement_day": "2022-02-02",
        "issuer_original_pdf_url":
            "https://static.cninfo.com.cn/finalpage/2022-02-02/123.PDF",
        "earliest_usable_exchange_day": "2022-02-03",
        "record_date": "2022-02-04", "ex_date": "2022-02-07",
    }
    with pytest.raises(ValueError, match="Missing or modified"):
        source_inventory([row], [tmp_path])


def test_wrong_published_date_path_fail_closed(tmp_path: Path):
    bad = tmp_path / "s.pdf"
    bad.write_bytes(b"%PDF-1.7 synthetic content")
    row = {
        "event_id": "fixture", "issuer_original_pdf_sha256": hashlib.sha256(
            bad.read_bytes()).hexdigest(),
        "announcement_day": "2022-02-02",
        "issuer_original_pdf_url":
            "https://static.cninfo.com.cn/finalpage/2022-02-01/123.PDF",
        "earliest_usable_exchange_day": "2022-02-03",
        "record_date": "2022-02-04", "ex_date": "2022-02-07",
    }
    with pytest.raises(ValueError, match="publication-day"):
        source_inventory([row], [tmp_path])


def test_wrong_intraday_retroactive_source_clock_fail_closed(tmp_path: Path):
    bad = tmp_path / "s.pdf"
    bad.write_bytes(b"%PDF-1.7 synthetic content")
    row = {
        "event_id": "fixture", "issuer_original_pdf_sha256": hashlib.sha256(
            bad.read_bytes()).hexdigest(),
        "announcement_day": "2022-02-02",
        "issuer_original_pdf_url":
            "https://static.cninfo.com.cn/finalpage/2022-02-02/123.PDF",
        "earliest_usable_exchange_day": "2022-02-02",
        "record_date": "2022-02-04", "ex_date": "2022-02-07",
    }
    with pytest.raises(ValueError, match="publication-clock"):
        source_inventory([row], [tmp_path])


def test_wrong_catalog_full_sha_blocks_output(tmp_path: Path):
    frozen = tmp_path / "wrong.json"
    frozen.write_text('{"issuer_events": 89}')
    dest = tmp_path / "new"
    with pytest.raises(ValueError, match="full catalog SHA256"):
        run(frozen, [], dest)
    assert not dest.exists()


def test_existing_output_cannot_be_overwritten(tmp_path: Path):
    folder = tmp_path / "already_present"
    folder.mkdir()
    with pytest.raises(FileExistsError, match="Never overwrite"):
        run(tmp_path / "missing.json", [], folder)
