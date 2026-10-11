"""Offline tests: invented CUSIPs and quotes; NO empirical trading claims."""
from datetime import date
import pytest
from src.research.cash_treasury import (
    TreasuryNote, BondQuote, clean_price_from_ytm, ytm_from_clean,
    bond_dv01_per_100, parse_auction_records, select_cash_notes,
    value_notes, construct_paper_fly, read_quotes,
)

DAY = date(2026, 9, 30)


def notes():
    return {
        5: TreasuryNote("912820A01", date(2023,1,31), date(2031,9,30), 3.875, "10-Year"),
        7: TreasuryNote("912820B02", date(2023,1,31), date(2033,9,30), 4.125, "10-Year"),
        10: TreasuryNote("912820C03", date(2023,1,31), date(2036,9,30), 4.25, "10-Year"),
    }


def test_bond_yield_price_inversion():
    bond = notes()[5]
    price = clean_price_from_ytm(bond, DAY, 3.8)
    assert ytm_from_clean(bond, DAY, price) == pytest.approx(3.8, abs=1e-8)
    assert bond_dv01_per_100(bond, DAY, 3.8) > 0


def test_auction_selection_and_deduplication():
    source = [
        dict(cusip=n.cusip, security_type="Note", security_term=n.original_term,
             issue_date=n.issue_date.isoformat(), auction_date="2023-01-30",
             maturity_date=n.maturity_date.isoformat(), int_rate=str(n.coupon_percent))
        for n in notes().values()
    ]
    source.append({**source[0], "issue_date":"2024-01-01", "auction_date":"2024-01-01"})
    selected = select_cash_notes(parse_auction_records(source, DAY), DAY)
    assert len({s.cusip for s in selected.values()}) == 3
    assert selected[5].issue_date == date(2023,1,31)


def test_quote_validation_rejects_stale_and_crossed(tmp_path):
    path = tmp_path/"quotes.csv"
    path.write_text("as_of,cusip,bid_clean,ask_clean,source\n2026-09-30,912820A01,99,100,broker_fixture\n")
    assert read_quotes(path, DAY)["912820A01"].mid_clean == 99.5
    with pytest.raises(ValueError, match="date"):
        read_quotes(path, date(2026,9,29))
    path.write_text("as_of,cusip,bid_clean,ask_clean,source\n2026-09-30,912820A01,100,99,broker_fixture\n")
    with pytest.raises(ValueError, match="Invalid"):
        read_quotes(path, DAY)


def test_model_value_hedge_and_costs():
    selection = notes()
    quotes = {}
    for n in selection.values():
        mid = clean_price_from_ytm(n, DAY, 4.)
        quotes[n.cusip] = BondQuote(n.cusip, DAY, mid-.025, mid+.025, "fixture")
    zero = {t: 4.+t*.005 for t in range(1,31)}
    values = value_notes(selection, quotes, DAY, zero)
    report = construct_paper_fly(values, 1, 300, min_face_increment=1)
    assert [v["hypothetical_side"] for v in report["legs"]] == ["SELL", "BUY", "SELL"]
    assert abs(report["rounded_level_dv01_usd_per_bp"]) < .5
    assert abs(report["rounded_tenor_weighted_dv01"]) < 3.
    assert report["total_half_spread_entry_cost_usd"] > 0


def test_fail_without_all_market_quotes():
    n = notes()
    with pytest.raises(ValueError, match="Missing exact-date"):
        value_notes(n, {n[5].cusip: BondQuote(n[5].cusip, DAY, 99,100,"fixture")}, DAY,
                    {t: 4. for t in range(1,31)})
    with pytest.raises(ValueError, match="Invalid paper"):
        construct_paper_fly({}, 2, 100)
