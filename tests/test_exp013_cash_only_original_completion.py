"""EXP013 synthetic guard tests; original public PDF/SHA replay is separate."""
import copy
from decimal import Decimal

import pytest

from quant_lab.pit_cash_only_original_completion import (
    SOURCE_GRADE, apply_direct_zero_proof, current_issuer_cash_only_clause,
)

BASE = (
    "某股份有限公司2021年年度权益分派实施公告。本公司本次仅进行现金红利分配，"
    "无送股和转增分配。因此，本公司流通股不会发生变化，流通股份变动比例为0。"
)


def fixture_event():
    return {
        "symbol": "SH600705",
        "ex_date": "2021-08-05",
        "issuer_original_pdf_sha256": "a" * 64,
        "bonus_shares_per_old_share": None,
        "capital_transfer_shares_per_old_share": None,
        "full_new_nominal_share_multiplier": None,
        "complete_rights_supported_by_issuer_original": False,
        "gross_cash_per_old_nominal_share": 0.112,
        "rights_evidence": {"bonus": "BONUS_UNCONFIRMED",
                            "transfer": "TRANSFER_UNCONFIRMED"},
        "broker_share_delivery_and_cash_payment_verified": False,
    }


def fixture_proof():
    return {
        "symbol": "SH600705",
        "ex_date": "2021-08-05",
        "original_issuer_pdf_sha256": "a" * 64,
        "source_evidence_grade": SOURCE_GRADE,
        "zero_bonus_and_transfer_direct_current_issuer_text": True,
        "unchanged_circulating_share_ratio_source_literal": True,
    }


@pytest.mark.parametrize("phrase", [
    "公司本次仅进行现金红利分配，无送股和转增分配，因此，公司流通股不会发生变化，流通股份变动比例为0。",
    "公司本次仅进行现金红利分配，无送股和转增股份，公司流通股不会发生变化，流通股份变动比例为0。",
    "本公司本次仅进行现金红利分配，无送股和转增分配。因此，本公司流通股不会发生变化，流通股份变动比例为0。",
])
def test_issuer_direct_current_cash_only_literal_and_zero_float_change(phrase):
    assert current_issuer_cash_only_clause(phrase)


@pytest.mark.parametrize("statement", [
    "公司拟仅派发现金股利，但送转方案尚待审议，流通股份变动比例为0。",
    "现金红利分配公告；派送红股或转增股本的，由登记公司按比例入账。",
    "公司本次仅进行现金红利分配，无送股和转增分配。流通股情况尚待确认。",
    "去年公司本次仅进行现金红利分配，无送股和转增分配，"
    "但本年度的流通股份变动比例为0。",
])
def test_weak_or_unrelated_text_must_not_prove_two_zeros(statement):
    assert not current_issuer_cash_only_clause(statement)


def test_contradictory_positive_stock_right_clause_fails_closed():
    with pytest.raises(ValueError, match="conflict"):
        current_issuer_cash_only_clause(BASE + "本次每10股送2股。")


def test_contradictory_positive_capital_transfer_fails_closed():
    with pytest.raises(ValueError, match="conflict"):
        current_issuer_cash_only_clause(BASE + "本次每10股转增3股。")


def test_overlay_only_derives_new_event_and_does_not_mutate_frozen_source():
    original = fixture_event()
    immutable = copy.deepcopy(original)
    upgraded = apply_direct_zero_proof(original, fixture_proof())
    assert original == immutable
    assert upgraded is not original
    assert upgraded["bonus_shares_per_old_share"] == 0.0
    assert upgraded["capital_transfer_shares_per_old_share"] == 0.0
    assert Decimal(str(upgraded["full_new_nominal_share_multiplier"])) == 1
    assert upgraded["complete_rights_supported_by_issuer_original"] is True
    assert upgraded["gross_cash_per_old_nominal_share"] == original["gross_cash_per_old_nominal_share"]
    assert upgraded["rights_evidence"]["bonus"] == SOURCE_GRADE
    assert upgraded["exp013_prior_rights_evidence"] == immutable["rights_evidence"]
    assert upgraded["broker_share_delivery_and_cash_payment_verified"] is False


def test_overlay_accepts_prior_verified_transfer_zero_but_keeps_prior_proof():
    row = fixture_event()
    row["capital_transfer_shares_per_old_share"] = 0.0
    row["rights_evidence"]["transfer"] = "EXPLICIT_ISSUER_ZERO_TRANSFER"
    upgraded = apply_direct_zero_proof(row, fixture_proof())
    assert upgraded["exp013_prior_rights_evidence"]["transfer"] == (
        "EXPLICIT_ISSUER_ZERO_TRANSFER")


def test_overlay_never_erases_existing_positive_bonus():
    row = fixture_event()
    row["bonus_shares_per_old_share"] = 0.2
    with pytest.raises(ValueError, match="positive"):
        apply_direct_zero_proof(row, fixture_proof())


def test_overlay_never_accepts_wrong_issuer_pdf_sha_or_ticker():
    row = fixture_event()
    bad_hash = fixture_proof()
    bad_hash["original_issuer_pdf_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="identity"):
        apply_direct_zero_proof(row, bad_hash)
    bad_ticker = fixture_proof()
    bad_ticker["symbol"] = "SZ000001"
    with pytest.raises(ValueError, match="identity"):
        apply_direct_zero_proof(row, bad_ticker)


def test_overlay_cannot_rebrand_old_fully_complete_event():
    row = fixture_event()
    row["complete_rights_supported_by_issuer_original"] = True
    with pytest.raises(ValueError, match="already complete"):
        apply_direct_zero_proof(row, fixture_proof())



def test_bad_pdf_bytes_are_rejected_by_complete_sha256_first():
    from quant_lab.pit_cash_only_original_completion import verify_original_issuer_cash_only
    row = fixture_event()
    row["issuer_original_pdf_url"] = "https://static.cninfo.com.cn/finalpage/fake.PDF"
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        verify_original_issuer_cash_only(row, b"%PDF-pretend-but-tampered")


def test_overlay_rejects_unproved_zero_literals():
    p = fixture_proof()
    p["unchanged_circulating_share_ratio_source_literal"] = False
    with pytest.raises(ValueError, match="identity"):
        apply_direct_zero_proof(fixture_event(), p)
