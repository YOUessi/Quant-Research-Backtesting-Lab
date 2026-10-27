"""EXP014 unit regressions; separate offline original PDF SHA replay is mandatory."""
import copy
from decimal import Decimal
from pathlib import Path

import pytest

from quant_lab.pit_exp014_rights_completion import (
    GRADE_SSE, GRADE_SZ, PINNED, append_source_proof, literal_issuer_dates,
    run, source_proves_both_zero, verify_source,
)

SH_HEAD = "证券代码：600276 江苏恒瑞医药股份有限公司2021年年度权益分派实施公告"
SH_DIRECT = (
    "公司本次仅进行现金红利分配，无送转方案，因此，"
    "公司流通股不会发生变化，流通股份变动比例为0。"
)
SH_ALT_HEAD = "证券代码：601225陕西煤业股份有限公司2020年年度权益分派实施公告"
SH_ALT = (
    "公司本次利润分配仅进行现金红利分配，即每股派发现金红利0.8元（含税），"
    "无送股和转增分配。公司流通股不会发生变化，流动股份变动比例为0。"
)
SZ_HEAD = "证券代码：300676 深圳华大基因股份有限公司2021年年度权益分派实施公告"
SZ_DIRECT = (
    "2021年度公司不实施以资本公积转增股本，不送红股。"
    "自本次权益分派方案披露至实施期间，公司股本总额及公司回购专用"
    "证券账户持有的股份数均未发生变化。"
    "本次实施的分配方案与公司2021年年度股东大会审议通过的分配方案一致。"
)


def _row(key=("SH600276", "2022-07-05")):
    pin = PINNED[key]
    return {
        "event_id": pin["event_id"], "symbol": key[0], "ex_date": key[1],
        "issuer_original_pdf_sha256": pin["sha256"],
        "complete_rights_supported_by_issuer_original": False,
        "bonus_shares_per_old_share": None,
        "capital_transfer_shares_per_old_share": None,
        "full_new_nominal_share_multiplier": None,
        "rights_evidence": {
            "bonus": "BONUS_UNCONFIRMED", "transfer": "TRANSFER_UNCONFIRMED"
        },
        "announcement_day": "2022-06-29", "earliest_usable_exchange_day": "2022-06-30",
        "record_date": "2022-07-04", "scheduled_cash_payment_day": "2022-07-05",
        "gross_cash_per_old_nominal_share": 0.16,
        "broker_share_delivery_and_cash_payment_verified": False,
    }


def _proof(key=("SH600276", "2022-07-05")):
    pin = PINNED[key]
    return {
        "event_id": pin["event_id"],
        "symbol": key[0], "ex_date": key[1],
        "issuer_pdf_sha256_full": pin["sha256"],
        "source_grade": pin["grade"], "both_zero_issuer_text": True,
    }


def test_sse_direct_current_only_cash_no_stock_transfer():
    assert source_proves_both_zero(SH_DIRECT, SH_HEAD, "2021", GRADE_SSE)


def test_sse_second_variant_with_issuer_typo_in_ratio_literal():
    assert source_proves_both_zero(SH_ALT, SH_ALT_HEAD, "2020", GRADE_SSE)


@pytest.mark.parametrize("bad", [
    "公司本次仅进行现金红利分配，无送转方案。",
    "去年公司本次仅进行现金红利分配，但今年送转方案尚未公布。",
    "公司本次利润分配仅进行现金红利分配，无送股和转增分配；"
    "流动股份变动比例为0。",
])
def test_sse_weak_statements_rejected(bad):
    assert not source_proves_both_zero(bad, SH_HEAD, "2021", GRADE_SSE)


def test_sse_wrong_fiscal_year_head_rejected():
    assert not source_proves_both_zero(SH_DIRECT, SH_ALT_HEAD, "2021", GRADE_SSE)


def test_sz_current_implemented_rights_complete_no_transfer():
    assert source_proves_both_zero(SZ_DIRECT, SZ_HEAD, "2021", GRADE_SZ)


@pytest.mark.parametrize("bad", [
    SZ_DIRECT.replace("本次实施的分配方案与公司", "上年实施的分配方案与公司"),
    SZ_DIRECT.replace("不实施以资本公积转增股本", "计划实施以资本公积转增股本"),
    SZ_DIRECT.replace("股本总额及公司回购专用", "此前的股本总额及公司回购专用"),
    SZ_DIRECT.replace("2021年度", "2020年度"),
])
def test_sz_outdated_plan_or_missing_current_implementation_refused(bad):
    assert not source_proves_both_zero(bad, SZ_HEAD, "2021", GRADE_SZ)


def test_sz_explicit_no_comma_original_dates_are_not_guessed():
    text = (
        "三、权益分派日期本次权益分派股权登记日为：2022年7月5日"
        "除权除息日为：2022年7月6日四、权益分派对象"
        "现金红利将于2022年7月6日通过证券公司划入资金账户。"
    )
    row = {"symbol": "SZ300676", "ex_date": "2022-07-06"}
    parsed = literal_issuer_dates(text, row)
    assert parsed["record_date"] == "2022-07-05"
    assert parsed["ex_date"] == "2022-07-06"
    assert parsed["pay_date"] == "2022-07-06"
    assert parsed["status"].startswith("PINNED_SZ_2022")


def test_sz_no_comma_dates_cannot_be_recovered_for_an_unreviewed_symbol():
    text = (
        "本次权益分派股权登记日为：2022年7月5日"
        "除权除息日为：2022年7月6日"
        "现金红利将于2022年7月6日通过证券公司到账。"
    )
    with pytest.raises(ValueError, match="unavailable"):
        literal_issuer_dates(text, {"symbol": "SZ000001", "ex_date": "2022-07-06"})


def test_new_proof_only_adds_unknown_categories_and_preserves_evidence():
    row = _row(("SZ300676", "2021-07-07"))
    row.update(announcement_day="2021-06-29", earliest_usable_exchange_day="2021-06-30",
               record_date="2021-07-06", scheduled_cash_payment_day="2021-07-07",
               gross_cash_per_old_nominal_share=0.35)
    row["bonus_shares_per_old_share"] = 0.0
    row["rights_evidence"]["bonus"] = "EXPLICIT_ISSUER_ZERO_BONUS"
    old = copy.deepcopy(row)
    out = append_source_proof(row, _proof(("SZ300676", "2021-07-07")))
    assert row == old
    assert out["complete_rights_supported_by_issuer_original"] is True
    assert out["exp014_newly_proven_stock_zero_categories"] == [
        "capital_transfer_shares_per_old_share"
    ]
    assert out["rights_evidence"]["bonus"] == "EXPLICIT_ISSUER_ZERO_BONUS"
    assert out["rights_evidence"]["transfer"] == GRADE_SZ
    assert Decimal(str(out["full_new_nominal_share_multiplier"])) == Decimal(1)
    assert out["gross_cash_per_old_nominal_share"] == 0.35
    assert out["broker_share_delivery_and_cash_payment_verified"] is False


def test_sse_new_proof_confirms_both_categories_without_old_mutation():
    row = _row()
    old = copy.deepcopy(row)
    out = append_source_proof(row, _proof())
    assert row == old
    assert out["exp014_newly_proven_stock_zero_categories"] == [
        "bonus_shares_per_old_share", "capital_transfer_shares_per_old_share"
    ]
    assert out["rights_evidence"] == {"bonus": GRADE_SSE, "transfer": GRADE_SSE}


def test_proof_fails_closed_on_existing_positive_share_entitlement():
    row = _row()
    row["bonus_shares_per_old_share"] = 0.2
    with pytest.raises(ValueError, match="positive"):
        append_source_proof(row, _proof())


def test_proof_fails_closed_on_identity_sha_and_claim_tampering():
    row = _row()
    for change in (
        {"source_grade": GRADE_SZ}, {"issuer_pdf_sha256_full": "a" * 64},
        {"symbol": "SH000001"}, {"both_zero_issuer_text": False},
    ):
        p = _proof()
        p.update(change)
        with pytest.raises(ValueError, match="identity"):
            append_source_proof(row, p)


def test_pdf_bytes_need_complete_exact_sha_first():
    row = _row()
    with pytest.raises(ValueError, match="SHA256"):
        verify_source(row, b"%PDF-1.7\\nsynthetic-modified-payload")


def test_already_complete_rights_never_reclassified():
    row = _row()
    row["complete_rights_supported_by_issuer_original"] = True
    with pytest.raises(ValueError, match="already complete"):
        append_source_proof(row, _proof())


def test_missing_or_mutated_prior_catalog_digest_rejected(tmp_path: Path):
    bogus = tmp_path / "catalog.json"
    bogus.write_text('{"kind":"fake","events":[]}', encoding="utf-8")
    dest = tmp_path / "new"
    with pytest.raises(ValueError, match="full SHA256 mismatch"):
        run(bogus, [], dest)
    assert not dest.exists()
