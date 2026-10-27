"""EXP018 guards; the Mac source replayer separately reads original PDF bytes."""
import copy
from decimal import Decimal

import pytest

from quant_lab.pit_exp018_treasury_cash_only import (
    BASE_SHA256, GRADE, PINNED, apply_proof,
    current_cash_only_treasury_proof, run, verify_source,
)

KEY = ("SZ002311", "2021-07-09")


def row(key=KEY):
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
        "announcement_day": "2021-07-02",
        "earliest_usable_exchange_day": "2021-07-05",
        "record_date": "2021-07-08",
        "scheduled_cash_payment_day": "2021-07-09",
        "gross_cash_per_old_nominal_share": .32,
        "issuer_original_pdf_url": "https://static.cninfo.com.cn/finalpage/2021-07-02/1210385811.PDF",
        "cash_rights_nominal_not_qlib_adjusted": True,
        "broker_share_delivery_and_cash_payment_verified": False,
        "historical_factor_vintage_available": False,
        "original_publication_intraday_time_certified": False,
    }


def sample(key=KEY):
    pin = PINNED[key]
    title = f"证券代码：{key[0][-6:]}{pin['name']}{pin['title']}"
    cash_per_ten = str(Decimal(pin["cash"]) * Decimal(10))
    with_commas = lambda n: f"{n:,}"
    s = (
        "特别提示：本次权益分派实施后，公司总股本保持不变。"
        "一、股东大会审议通过利润分配方案的情况其他公司背景。"
        "二、本次实施的权益分派方案"
        "本公司权益分派方案为："
        "以公司现有总股本剔除已回购股份"
        + with_commas(pin["treasury"]) + "股后的"
        + with_commas(pin["eligible"]) + "股为基数，"
        "向全体股东每10股派" + cash_per_ten
        + "元人民币现金（含税）。"
        "三、股权登记日与除权除息日声明。"
        "四、权益分派对象。五、权益分派方法。"
        "六、关于除权除息价的计算原则及方式"
        "本次权益分派实施后，公司总股本保持不变。"
        "每股现金红利=实际现金分红总额÷总股本="
        + f"{Decimal(pin['total']):,.2f}" + "÷"
        + with_commas(pin["issued"]) + "=" + pin["ex_cash"] + "元/股。"
        "七、关于股权激励计划若将来发生转增则另行调整。"
    )
    return s, title


def audit_proof(key=KEY):
    p = PINNED[key]
    return {
        "event_id": p["event_id"], "source_full_sha256": p["sha256"],
        "source_grade": GRADE, "current_issuer_no_new_shares": True,
        "issuer_total_shares": p["issued"],
        "treasury_shares_excluded_from_distribution": p["treasury"],
        "issuer_cash_eligible_shares": p["eligible"],
        "cash_reference_not_holder_cash_claim": True,
        "gross_cash_per_cash_eligible_share": p["cash"],
        "ex_price_reference_cash_per_issued_share": p["ex_cash"],
        "actual_broker_cash_or_stock_credit_verified": False,
    }


@pytest.mark.parametrize("key", list(PINNED))
def test_cash_only_current_capital_and_reference_not_holder_claim(key):
    body, head = sample(key)
    p = current_cash_only_treasury_proof(body, head, key[0], PINNED[key])
    assert p is not None
    assert p["issuer_total_shares"] == (
        p["treasury_shares_excluded_from_distribution"]
        + p["issuer_cash_eligible_shares"])
    assert Decimal(p["ex_price_reference_cash_per_issued_share"]) < (
        Decimal(p["gross_cash_per_cash_eligible_share"]))
    assert p["current_issuer_no_new_shares"] is True


@pytest.mark.parametrize("mutate", [
    lambda s, h, p: (s, h.replace("002311", "002312"), p),
    lambda s, h, p: (s, h.replace("广东海大集团股份有限公司", "其他公司"), p),
    lambda s, h, p: (s, h.replace("2020年年度", "2021年年度"), p),
    lambda s, h, p: (s.replace("特别提示：本次权益分派实施后，公司总股本保持不变。",
                                "特别提示：拟进行现金分红。"), h, p),
    lambda s, h, p: (s.replace("六、关于除权除息价的计算原则及方式"
                                "本次权益分派实施后，公司总股本保持不变。",
                                "六、关于除权除息价的计算原则及方式"), h, p),
    lambda s, h, p: (s.replace("每10股派3.20元", "每10股送2股，每10股派3.20元"), h, p),
    lambda s, h, p: (s.replace("每10股派3.20元", "每10股派3.20元，同时转增2股"), h, p),
    lambda s, h, p: (s.replace("10,272,108股", "10,272,109股"), h, p),
    lambda s, h, p: (s.replace("1,650,888,953股", "1,650,888,952股"), h, p),
    lambda s, h, p: (s.replace("每10股派3.20元", "每10股派3.30元"), h, p),
    lambda s, h, p: (s.replace("528,284,464.96", "528,284,464.95"), h, p),
    lambda s, h, p: (s.replace("0.3180212元/股", "0.3200000元/股"), h, p),
    lambda s, h, p: (s.replace("二、本次实施的权益分派方案", "二、假设中的权益分派方案"), h, p),
    lambda s, h, p: (s.replace("以公司现有总股本剔除已回购股份",
                                "公司任意登记日股数为"), h, p),
])
def test_reject_false_sources_even_with_current_cash_words(mutate):
    body, head = sample(KEY)
    body, head, pin = mutate(body, head, PINNED[KEY])
    assert current_cash_only_treasury_proof(body, head, KEY[0], pin) is None


def test_pinned_sources_all_distinct_and_full_length():
    assert len(PINNED) == 3
    assert len({p["sha256"] for p in PINNED.values()}) == 3
    assert all(len(p["sha256"]) == 64 for p in PINNED.values())
    assert len(BASE_SHA256) == 64


def test_mutated_original_bytes_rejected_before_parsing():
    with pytest.raises(ValueError, match="SHA256"):
        verify_source(row(), b"%PDF-1.7\nforged content")


def test_outside_pinned_scope_refused():
    r = row()
    r["symbol"] = "SZ300751"
    with pytest.raises(ValueError, match="Unreviewed"):
        verify_source(r, b"%PDF-1.7\n")


def test_upgraded_rights_preserve_cash_credit_source_and_time():
    r = row()
    before = copy.deepcopy(r)
    after = apply_proof(r, audit_proof())
    assert before == r
    assert after["complete_rights_supported_by_issuer_original"]
    assert (after["bonus_shares_per_old_share"],
            after["capital_transfer_shares_per_old_share"],
            after["full_new_nominal_share_multiplier"]) == (0, 0, 1)
    assert after["rights_evidence"] == {"bonus": GRADE, "transfer": GRADE}
    assert after["exp018_previous_rights_evidence"] == before["rights_evidence"]
    assert after["exp018_original_issuer_treasury_cash_proof"] == audit_proof()
    for k in ("announcement_day", "earliest_usable_exchange_day",
              "record_date", "ex_date", "scheduled_cash_payment_day",
              "gross_cash_per_old_nominal_share", "issuer_original_pdf_sha256",
              "issuer_original_pdf_url", "cash_rights_nominal_not_qlib_adjusted",
              "broker_share_delivery_and_cash_payment_verified",
              "historical_factor_vintage_available",
              "original_publication_intraday_time_certified"):
        assert before[k] == after[k]


@pytest.mark.parametrize("alter", [
    {"event_id": "wrong"}, {"source_full_sha256": "f"*64},
    {"source_grade": "NO_SOURCE"}, {"current_issuer_no_new_shares": False},
    {"issuer_total_shares": 1}, {"treasury_shares_excluded_from_distribution": 0},
    {"issuer_cash_eligible_shares": 1},
    {"gross_cash_per_cash_eligible_share": "0.3180212"},
    {"ex_price_reference_cash_per_issued_share": "0.32"},
    {"cash_reference_not_holder_cash_claim": False},
    {"actual_broker_cash_or_stock_credit_verified": True},
])
def test_forged_documented_proof_is_not_accepted(alter):
    proof = audit_proof()
    proof.update(alter)
    with pytest.raises(ValueError, match="Unverified"):
        apply_proof(row(), proof)


@pytest.mark.parametrize("field,value", [
    ("complete_rights_supported_by_issuer_original", True),
    ("bonus_shares_per_old_share", 0.0),
    ("capital_transfer_shares_per_old_share", 0.0),
    ("full_new_nominal_share_multiplier", 1.0),
])
def test_existing_claim_cannot_be_reinterpreted_as_unknown(field, value):
    r = row()
    r[field] = value
    with pytest.raises(ValueError, match="Unverified"):
        apply_proof(r, audit_proof())


def test_wrong_parent_full_hash_rejected_before_new_files(tmp_path):
    source = tmp_path / "wrong_catalog.json"
    source.write_text('{"issuer_events":89}', encoding="utf-8")
    out = tmp_path / "new"
    with pytest.raises(ValueError, match="SHA256"):
        run(source, [], out)
    assert not out.exists()


def test_no_existing_evidence_destination_overwrite(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(FileExistsError):
        run(tmp_path / "absent.json", [], out)
