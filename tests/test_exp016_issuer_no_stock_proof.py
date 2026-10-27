"""Pure unit regression tests; separate Mac offline replay validates actual PDF SHA."""
import copy
from decimal import Decimal

import pytest

from quant_lab.pit_exp016_issuer_no_stock_proof import (
    BASE_SHA256, DIRECT, GRADE, PINNED, TITLE_NAME,
    apply_proof, run, source_proves_no_stock, verify_source,
)

HEAD = (
    "证券代码：600887 证券简称：伊利股份 "
    + TITLE_NAME + "2020年年度权益分派实施公告"
)
BODY = (
    "一、分配方案 二、股权登记日 三、相关日期 "
    "四、分配实施办法 (1) 现金红利派发 (2)"
    + DIRECT + "。五、其他事项"
)


def _old_row(key=("SH600887", "2021-06-11")):
    pin = PINNED[key]
    return {
        "event_id": pin["event_id"], "symbol": key[0], "ex_date": key[1],
        "issuer_original_pdf_sha256": pin["sha256"],
        "rights_evidence": {"bonus": "BONUS_UNCONFIRMED",
                            "transfer": "TRANSFER_UNCONFIRMED"},
        "bonus_shares_per_old_share": None,
        "capital_transfer_shares_per_old_share": None,
        "full_new_nominal_share_multiplier": None,
        "complete_rights_supported_by_issuer_original": False,
        "announcement_day": "2021-06-03",
        "earliest_usable_exchange_day": "2021-06-04",
        "record_date": "2021-06-10",
        "scheduled_cash_payment_day": "2021-06-11",
        "gross_cash_per_old_nominal_share": 0.82,
        "issuer_original_pdf_url":
            "https://static.cninfo.com.cn/finalpage/2021-06-03/1210151060.PDF",
        "cash_rights_nominal_not_qlib_adjusted": True,
        "broker_share_delivery_and_cash_payment_verified": False,
        "historical_factor_vintage_available": False,
        "original_publication_intraday_time_certified": False,
    }


def _proof(key=("SH600887", "2021-06-11")):
    pin = PINNED[key]
    return {
        "event_id": pin["event_id"], "symbol": key[0],
        "ex_date": key[1], "source_full_sha256": pin["sha256"],
        "source_grade": GRADE, "explicit_current_no_bonus_and_no_capital": True,
    }


def test_original_current_issuer_clause_is_sufficient_only_inside_implementation():
    assert source_proves_no_stock(BODY, HEAD, "2020")
    assert source_proves_no_stock(
        BODY.replace(" (2)", "2、").replace("。五、", "。(二) 五、"), HEAD, "2020"
    )


@pytest.mark.parametrize("body,head,year", [
    (BODY.replace(DIRECT, "如涉及派送红股或转增股本"), HEAD, "2020"),
    (BODY.replace(DIRECT, "本次权益分派涉及派送红股或转增股本"), HEAD, "2020"),
    (BODY.replace("四、分配实施办法", "四、通用登记程序"), HEAD, "2020"),
    (DIRECT + " 四、分配实施办法", HEAD, "2020"),
    (BODY, HEAD.replace("600887", "600888"), "2020"),
    (BODY, HEAD.replace(TITLE_NAME, "其他公司"), "2020"),
    (BODY, HEAD, "2021"),
    (BODY + DIRECT, HEAD, "2020"),
])
def test_no_stock_clause_rejects_weak_wrong_year_boilerplate(body, head, year):
    assert not source_proves_no_stock(body, head, year)


def test_exact_source_hash_or_identity_mismatch_rejected_before_pdf_parser():
    row = _old_row()
    with pytest.raises(ValueError, match="SHA256"):
        verify_source(row, b"%PDF-1.7\nforged input")


def test_wrong_issuer_proof_key_rejected():
    row = _old_row()
    row["symbol"] = "SZ000001"
    with pytest.raises(ValueError, match="Unreviewed"):
        verify_source(row, b"%PDF-1.7\nfake")


def test_two_original_issuer_pins_do_not_alias():
    assert len(PINNED) == 2
    assert len({p["sha256"] for p in PINNED.values()}) == 2
    assert len({p["event_id"] for p in PINNED.values()}) == 2
    assert len(BASE_SHA256) == 64


def test_approved_source_proof_only_fills_two_zeros():
    row = _old_row()
    original = copy.deepcopy(row)
    upgraded = apply_proof(row, _proof())
    assert row == original
    assert upgraded["bonus_shares_per_old_share"] == 0.0
    assert upgraded["capital_transfer_shares_per_old_share"] == 0.0
    assert Decimal(str(upgraded["full_new_nominal_share_multiplier"])) == 1
    assert upgraded["rights_evidence"]["bonus"] == GRADE
    assert upgraded["rights_evidence"]["transfer"] == GRADE
    assert upgraded["exp016_previous_rights_evidence"] == original["rights_evidence"]
    for name in (
        "scheduled_cash_payment_day", "gross_cash_per_old_nominal_share",
        "announcement_day", "earliest_usable_exchange_day", "record_date",
        "broker_share_delivery_and_cash_payment_verified",
        "historical_factor_vintage_available",
    ):
        assert upgraded[name] == original[name]


@pytest.mark.parametrize("change", [
    {"source_full_sha256": "a" * 64},
    {"event_id": "WRONG"},
    {"source_grade": "UNREVIEWED"},
    {"explicit_current_no_bonus_and_no_capital": False},
])
def test_modified_proof_metadata_rejected(change):
    row, proof = _old_row(), _proof()
    proof.update(change)
    with pytest.raises(ValueError, match="Source identity"):
        apply_proof(row, proof)


@pytest.mark.parametrize("field,value", [
    ("bonus_shares_per_old_share", Decimal("0.1")),
    ("capital_transfer_shares_per_old_share", 0.0),
    ("complete_rights_supported_by_issuer_original", True),
])
def test_never_overwrite_any_old_stock_right(field, value):
    row = _old_row()
    row[field] = value
    with pytest.raises(ValueError, match="rights already established"):
        apply_proof(row, _proof())


def test_nonexistent_or_wrong_baseline_does_not_create_a_derived_catalog(tmp_path):
    bad = tmp_path / "catalog.json"
    bad.write_text('{"issuer_events":89}', encoding="utf-8")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="full SHA256 mismatch"):
        run(bad, [], output)
    assert not output.exists()
