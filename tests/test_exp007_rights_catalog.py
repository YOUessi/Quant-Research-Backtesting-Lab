"""Original-publisher complete/unknown shares remain distinct in merged catalog."""
import copy
import pytest

from quant_lab.pit_rights_catalog import assemble


def fixture(bonus=.2,transfer=None,inferred="transfer"):
    event={
        "event_id":"x","symbol":"SH600276","announcement_day":"2021-06-04",
        "earliest_usable_exchange_day":"2021-06-07",
        "record_date":"2021-06-09","ex_date":"2021-06-10",
        "payment_date":"2021-06-11","gross_cash_per_nominal_share":.2,
        "issuer_pdf_sha256":"a"*64,
        "issuer_pdf_url":"https://static.cninfo.com.cn/finalpage/doc.PDF",
    }
    cash={"kind":"EXP005_CANONICAL_ISSUER_CASH_ENTITLEMENT_LEDGER",
          "events":[event]*89}
    # Need unique IDs to test actual source merges without overwriting IDs.
    cash["events"]=[{**event,"event_id":f"id{i}"} for i in range(89)]
    rights={"kind":"EXP006_ORIGINAL_ISSUER_STOCK_DISTRIBUTION_AND_TRANSFER_AUDIT",
            "audit":[]}
    cap={"kind":"EXP007_CORPORATE_CAPITAL_BALANCE_ADDITIONAL_NO_RIGHT_PROOF",
         "audits":[]}
    for e in cash["events"]:
        rights["audit"].append({
            "event_id":e["event_id"],"issuer_pdf_sha256":e["issuer_pdf_sha256"],
            "bonus_ratio_per_nominal_share":bonus,
            "transfer_ratio_per_nominal_share":transfer,
            "bonus_source_status":"EXPLICIT_ISSUER_PER_SHARE_BONUS",
            "transfer_source_status":"TRANSFER_UNCONFIRMED",
        })
        cap["audits"].append({
            "event_id":e["event_id"],"original_pdf_sha256":e["issuer_pdf_sha256"],
            "balanced_accounting_inferred_zero_category":inferred,
            "status":"ISSUER_IN_SAME_PDF_PRE_POST_AND_ISSUED_SHARE_BALANCE_SUPPORT_ZERO_COMPLEMENT",
            "pre_nominal_company_shares":100_000_000,
            "post_nominal_company_shares":120_000_000,
            "issuer_explicit_new_share_quantity":20_000_000,
        })
    return cash,rights,cap


def test_complement_zero_is_derived_and_audited_not_assumed():
    cash,rights,capital=fixture()
    x=assemble(cash,rights,capital)
    assert x["fully_verified_nominal_share_rights"]==89
    assert x["derived_zero_category_by_balanced_issuer_company_shares"]==89
    item=x["events"][0]
    assert item["full_new_nominal_share_multiplier"]==pytest.approx(1.2)
    assert item["rights_evidence"]["transfer"].startswith("DERIVED")
    assert not item["broker_share_delivery_and_cash_payment_verified"]


def test_without_same_document_balance_unknown_remains_unknown():
    cash,rights,capital=fixture(inferred=None)
    for d in capital["audits"]:
        d["status"]="NO_SINGLE_ELIGIBLE_ISSUER_CAPITAL_BALANCE"
    out=assemble(cash,rights,capital)
    assert out["fully_verified_nominal_share_rights"]==0
    assert out["unknown_share_rights"]==89
    assert out["partial_positive_stock_rights"]==89


def test_unresolved_or_inconsistent_source_proof_fails_closed():
    cash,rights,capital=fixture()
    capital["audits"][0]["original_pdf_sha256"]="b"*64
    with pytest.raises(ValueError,match="identity mismatch"):
        assemble(cash,rights,capital)


def test_cannot_fabricate_complementary_zero_without_positive_right():
    cash,rights,capital=fixture()
    rights["audit"][0]["bonus_ratio_per_nominal_share"]=None
    with pytest.raises(ValueError,match="conflicts"):
        assemble(cash,rights,capital)
