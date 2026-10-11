"""Strict fake-record tests: government-account reference, NOT tradable quotes."""
from datetime import date
import pytest
from src.data.fip_prices import parse_fedinvest_rows


def fake(**kwargs):
    row = {
        "data_date": "2026-09-30", "cusip": "91282CRN3",
        "security_type": "MARKET BASED NOTE",
        "buy_amt": "99.90", "sell_amt": "99.80", "end_of_day_amt": "99.85",
    }
    row.update(kwargs)
    return row


def test_note_prices_are_attributed_and_not_broker_quotes():
    prices = parse_fedinvest_rows(
        [fake()], "https://api.fiscaldata.treasury.gov/reference",
        date(2026,9,30), date(2026,9,30))
    assert len(prices) == 1
    assert prices[0].reference_mid_per_100 == pytest.approx(99.85)
    assert prices[0].indicative_half_spread_per_100 == pytest.approx(.05)


def test_no_fake_missing_quotes():
    prices = parse_fedinvest_rows(
        [fake(buy_amt="0"), fake(data_date="2026-10-01",cusip="91282CRM5",sell_amt="0")],
        "https://api.fiscaldata.treasury.gov",
        date(2026,9,30), date(2026,10,1))
    assert not prices


def test_duplicate_and_crossed_reference_fails():
    args = ("https://api.fiscaldata.treasury.gov",date(2026,9,30),date(2026,9,30))
    with pytest.raises(ValueError,match="Duplicate"):
        parse_fedinvest_rows([fake(),fake()],*args)
    with pytest.raises(ValueError,match="Crossed"):
        parse_fedinvest_rows([fake(buy_amt="99.5",sell_amt="99.8")],*args)


def test_reject_bad_dates_and_wrong_security():
    args = ("https://api.fiscaldata.treasury.gov",date(2026,9,30),date(2026,9,30))
    assert parse_fedinvest_rows([fake(security_type="MARKET BASED BILL")],*args) == []
    with pytest.raises(ValueError,match="outside"):
        parse_fedinvest_rows([fake(data_date="2026-09-29")],*args)
