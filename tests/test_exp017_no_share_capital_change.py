"""Unit/negative guards. The Mac replay checks actual 89 issuer source PDF bytes."""
import copy
from decimal import Decimal

import pytest

from quant_lab.pit_exp017_no_share_capital_change import (
    BASE_SHA256, CLAIM, GRADE, NAME, PINNED,
    apply_proof, current_no_capital_change, run, verify_source,
)

KEY = ("SZ300142", "2021-05-19")
TITLE = f"证券代码：300142证券简称：沃森生物{NAME}2020年年度权益分派实施公告"
BODY = (
    "一、股东大会审议情况及权益分派方案"
    "4、权益分派方案公司2020年年度权益分派方案为："
    "以本权益分派实施公告中确定的股权登记日当日的公司总股本为基数，"
    "向全体股东每10股派0.50元人民币现金（含税）。"
    "二、股权登记日与除权除息日2021年5月18日，2021年5月19日。"
    "四、权益分派方法公司此次委托中国结算深圳分公司代派A股股东现金红利。"
    "五、公司总股本变动情况分红前公司总股本为1,566,186,984股，"
    "分红后总股本为1,566,186,984股。"
    + CLAIM + "。六、调整相关参数"
    "若发生资本公积转增股本、派送股票红利，应调整行权价格。"
)


def old_row():
    pin = PINNED[KEY]
    return {
        "event_id": pin["event_id"], "symbol": KEY[0], "ex_date": KEY[1],
        "issuer_original_pdf_sha256": pin["sha256"],
        "rights_evidence": {"bonus": "BONUS_UNCONFIRMED",
                            "transfer": "TRANSFER_UNCONFIRMED"},
        "bonus_shares_per_old_share": None,
        "capital_transfer_shares_per_old_share": None,
        "full_new_nominal_share_multiplier": None,
        "complete_rights_supported_by_issuer_original": False,
        "announcement_day": "2021-05-12",
        "earliest_usable_exchange_day": "2021-05-13",
        "record_date": "2021-05-18",
        "scheduled_cash_payment_day": "2021-05-19",
        "gross_cash_per_old_nominal_share": .05,
        "issuer_original_pdf_url":
            "https://static.cninfo.com.cn/finalpage/2021-05-12/1209958626.PDF",
        "cash_rights_nominal_not_qlib_adjusted": True,
        "broker_share_delivery_and_cash_payment_verified": False,
        "historical_factor_vintage_available": False,
        "original_publication_intraday_time_certified": False,
    }


def proof():
    pin = PINNED[KEY]
    return {
        "event_id": pin["event_id"],
        "source_full_sha256": pin["sha256"],
        "source_grade": GRADE,
        "issuer_current_plan_no_stock_issuance": True,
        "issuer_declared_before_and_after_total": pin["share_capital"],
    }


def test_exact_current_cash_only_plan_and_no_issued_capital_change():
    assert current_no_capital_change(BODY, TITLE, "2020", 1566186984)


@pytest.mark.parametrize("body,head,fiscal,total", [
    (BODY, TITLE.replace("300142", "300143"), "2020", 1566186984),
    (BODY, TITLE.replace(NAME, "其他股份有限公司"), "2020", 1566186984),
    (BODY, TITLE, "2021", 1566186984),
    (BODY.replace(CLAIM, "本次分红只含现金"), TITLE, "2020", 1566186984),
    (BODY.replace("分红后总股本为1,566,186,984", "分红后总股本为1,566,186,985"),
     TITLE, "2020", 1566186984),
    (BODY, TITLE, "2020", 1566186985),
    (BODY.replace("五、公司总股本变动情况", "五、预案讨论"), TITLE, "2020", 1566186984),
    (BODY.replace("六、调整相关参数", "六、其他事项"), TITLE, "2020", 1566186984),
    (BODY.replace("四、权益分派方法", "四、一般结算说明"),
     TITLE, "2020", 1566186984),
    (BODY.replace("向全体股东每10股派", "本次计划曾经每10股派"),
     TITLE, "2020", 1566186984),
    (BODY.replace("向全体股东每10股派0.50元", "向全体股东每10股派0.50元并转增2股"),
     TITLE, "2020", 1566186984),
    (BODY.replace("向全体股东每10股派0.50元", "向全体股东每10股送红股2股，另派0.50元"),
     TITLE, "2020", 1566186984),
    (BODY.replace("向全体股东每10股派0.50元",
                  "向全体股东每10股派0.50元；同时，以资本公积金"),
     TITLE, "2020", 1566186984),
    (BODY.replace("五、公司总股本变动情况",
                  CLAIM+"。五、公司总股本变动情况"),
     TITLE, "2020", 1566186984),
])
def test_reject_changed_forecast_other_issuer_broker_or_positive_rights(
    body, head, fiscal, total,
):
    assert not current_no_capital_change(body, head, fiscal, total)


def test_header_generic_sse_differential_is_not_proof():
    bad_body = BODY.replace(CLAIM, "差异化分红送转：否")
    assert not current_no_capital_change(bad_body, TITLE, "2020", 1566186984)


def test_pins_are_distinct_full_hashes_and_source_immutable():
    assert len(PINNED) == 2
    assert len({p["event_id"] for p in PINNED.values()}) == 2
    assert len({p["sha256"] for p in PINNED.values()}) == 2
    assert len(BASE_SHA256) == 64


def test_missing_real_original_bytes_rejected_before_pdf_parser():
    with pytest.raises(ValueError, match="SHA256"):
        verify_source(old_row(), b"%PDF-1.7\nnot the real original")


def test_wrong_original_event_cannot_be_used():
    row = old_row()
    row["symbol"] = "SH600887"
    with pytest.raises(ValueError, match="Unreviewed"):
        verify_source(row, b"%PDF-1.7")


def test_rights_zero_upgrade_preserves_source_cash_and_credit():
    row = old_row()
    saved = copy.deepcopy(row)
    newer = apply_proof(row, proof())
    assert row == saved
    assert newer["complete_rights_supported_by_issuer_original"] is True
    assert newer["bonus_shares_per_old_share"] == 0
    assert newer["capital_transfer_shares_per_old_share"] == 0
    assert Decimal(str(newer["full_new_nominal_share_multiplier"])) == 1
    assert newer["rights_evidence"] == {"bonus": GRADE, "transfer": GRADE}
    assert newer["exp017_previous_rights_evidence"] == saved["rights_evidence"]
    for field in ("issuer_original_pdf_sha256", "issuer_original_pdf_url",
                  "announcement_day", "earliest_usable_exchange_day",
                  "record_date", "ex_date", "scheduled_cash_payment_day",
                  "gross_cash_per_old_nominal_share",
                  "broker_share_delivery_and_cash_payment_verified",
                  "historical_factor_vintage_available"):
        assert newer[field] == saved[field]


@pytest.mark.parametrize("mutate", [
    {"source_full_sha256": "b" * 64},
    {"event_id": "wrong"},
    {"source_grade": "VENDOR_GUESSED"},
    {"issuer_current_plan_no_stock_issuance": False},
    {"issuer_declared_before_and_after_total": 0},
])
def test_reject_forged_mutated_audit_proof(mutate):
    p = proof()
    p.update(mutate)
    with pytest.raises(ValueError, match="not verified"):
        apply_proof(old_row(), p)


@pytest.mark.parametrize("field,value", [
    ("bonus_shares_per_old_share", 0.1),
    ("capital_transfer_shares_per_old_share", 0.0),
    ("full_new_nominal_share_multiplier", 1.0),
    ("complete_rights_supported_by_issuer_original", True),
])
def test_do_not_overwrite_any_existing_right_claim(field, value):
    row = old_row()
    row[field] = value
    with pytest.raises(ValueError, match="not verified"):
        apply_proof(row, proof())


def test_bad_frozen_catalog_rejected_without_writing(tmp_path):
    parent = tmp_path / "source.json"
    parent.write_text('{"issuer_events":89}', encoding="utf-8")
    dest = tmp_path / "new"
    with pytest.raises(ValueError, match="SHA256"):
        run(parent, [], dest)
    assert not dest.exists()


def test_no_prior_run_can_be_overwritten(tmp_path):
    dest = tmp_path / "already_there"
    dest.mkdir()
    with pytest.raises(FileExistsError):
        run(tmp_path / "missing.json", [], dest)
