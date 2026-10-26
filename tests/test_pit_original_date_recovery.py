"""Issuer text of record/ex/pay dates independent of aggregator response."""
import pytest

from quant_lab.pit_original_date_recovery import (
    issuer_implementation_dates, normalize_date,
)


def test_sh_ex_and_pay_same_date_are_not_merged():
    text=(
        "股份类别股权登记日最后交易日除权（息）日现金红利发放日"
        "Ａ股2021/5/20－2021/5/212021/5/21"
    )
    dates=issuer_implementation_dates(text,"SH600068")
    assert dates=={
        "record_date":"2021-05-20","ex_date":"2021-05-21",
        "pay_date":"2021-05-21",
        "status":"PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED",
    }


def test_sz_announced_register_and_ex_without_guessing_pay_date():
    text=(
        "三、股权登记日与除权除息日"
        "本次权益分派股权登记日为：2022年6月1日，"
        "除权除息日为：2022年6月2日。"
    )
    dates=issuer_implementation_dates(text,"SZ000627")
    assert dates["record_date"]=="2022-06-01"
    assert dates["ex_date"]=="2022-06-02"
    assert dates["pay_date"] is None
    assert dates["status"]=="PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED"


def test_sz_pay_date_must_be_unambiguously_in_issuer_pdf():
    text=(
        "本次权益分派股权登记日为：2022年7月21日，"
        "除权除息日为：2022年7月22日。"
        "A股股东现金红利将于2022年7月22日通过"
    )
    dates=issuer_implementation_dates(text,"SZ000001")
    assert dates["pay_date"]=="2022-07-22"


def test_late_pay_or_invalid_chronology_fails():
    text=(
        "本次权益分派股权登记日为：2022年7月25日，"
        "除权除息日为：2022年7月22日。"
    )
    with pytest.raises(ValueError,match="chronology"):
        issuer_implementation_dates(text,"SZ000001")
