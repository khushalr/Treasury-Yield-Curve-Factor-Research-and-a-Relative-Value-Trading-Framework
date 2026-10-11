"""Official FedInvest Government Account Series reference prices (NOT dealer quotes).

Fiscal Data: https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/fip_rates_prices
The buy/sell fields apply to mirror-image *government account* securities.
They are unsuitable as assertions of executable secondary-market bid/ask.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Iterable, Mapping


@dataclass(frozen=True)
class FedInvestReferencePrice:
    date: date
    cusip: str
    security_type: str
    reference_buy_per_100: float
    reference_sell_per_100: float
    reference_eod_per_100: float | None
    source_url: str

    @property
    def reference_mid_per_100(self) -> float:
        return (self.reference_buy_per_100 + self.reference_sell_per_100) / 2

    @property
    def indicative_half_spread_per_100(self) -> float:
        return (self.reference_buy_per_100 - self.reference_sell_per_100) / 2


def _positive_number(value: object) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and 0 < number < 500 else None


def parse_fedinvest_rows(rows: Iterable[Mapping[str, object]],
                         source_url: str,
                         start: date, end: date) -> list[FedInvestReferencePrice]:
    """Fail on duplicates and malformed note prices; discard other security types.

    Buy is the government-account purchase reference, sell the redemption
    reference. They are NOT necessarily executable broker ask/bid.
    Zero values are missing prices, never free securities.
    """
    if not source_url.startswith("https://"):
        raise ValueError("Must retain HTTPS provenance.")
    if start > end:
        raise ValueError("start date after end date.")
    result: list[FedInvestReferencePrice] = []
    seen: set[tuple[date, str]] = set()
    for row in rows:
        type_name = str(row.get("security_type", "")).upper().strip()
        if "NOTE" not in type_name or "TIPS" in type_name or "FLOAT" in type_name:
            continue
        raw_date = str(row.get("data_date", ""))
        try:
            observation = date.fromisoformat(raw_date[:10])
        except ValueError as exc:
            raise ValueError(f"Invalid FedInvest data_date {raw_date!r}") from exc
        if not start <= observation <= end:
            raise ValueError(f"Observation outside requested date interval: {observation}")
        cusip = str(row.get("cusip", "")).strip().upper()
        if len(cusip) != 9 or not cusip.isalnum():
            raise ValueError(f"Invalid CUSIP {cusip!r}")
        key = (observation, cusip)
        if key in seen:
            raise ValueError(f"Duplicate price date/CUSIP: {observation} {cusip}")
        seen.add(key)
        buy = _positive_number(row.get("buy_amt"))
        sell = _positive_number(row.get("sell_amt"))
        if buy is None or sell is None:
            continue   # No usable 2-sided government-account reference on this day
        if buy < sell:
            raise ValueError(f"Crossed government-account reference for {cusip} {observation}")
        eod = _positive_number(row.get("end_of_day_amt"))
        result.append(FedInvestReferencePrice(
            date=observation, cusip=cusip, security_type=type_name,
            reference_buy_per_100=buy, reference_sell_per_100=sell,
            reference_eod_per_100=eod, source_url=source_url,
        ))
    return sorted(result, key=lambda q: (q.date, q.cusip))


def prepare_reference_panel(
    refs: Iterable[FedInvestReferencePrice],
    auction_records: list[dict],
    fed_curve,
    *,
    min_seasoning_days: int = 90,
    max_maturity_gap_years: float = .85,
):
    """Daily 5/7/10 CUSIP-level valuations from government ACCOUNT references.

    Dates missing the full curve or any of the three references are marked
    missing; NEVER carried forward. No signals, no P&L, no broker orders.
    """
    from src.research.cash_treasury import (
        parse_auction_records, select_cash_notes, TreasuryNote,
        ytm_from_clean, bond_dv01_per_100, price_from_zero_curve,
    )
    import pandas as pd
    by_day: dict[date, dict[str, FedInvestReferencePrice]] = {}
    for ref in refs:
        if ref.cusip in by_day.setdefault(ref.date, {}):
            raise ValueError("Duplicate CUSIP-date in reference panel.")
        by_day[ref.date][ref.cusip] = ref
    rows: list[dict] = []
    omissions: list[dict] = []
    for day in sorted(by_day):
        selected: dict[int, TreasuryNote] = {}
        try:
            universe = parse_auction_records(auction_records, day)
            selected = select_cash_notes(universe, day,
                minimum_age_days=min_seasoning_days,
                maximum_maturity_gap_years=max_maturity_gap_years)
            stamp = pd.Timestamp(day)
            if stamp not in fed_curve.index:
                raise ValueError("Fed model-curve observation missing on reference date.")
            fed = fed_curve.loc[stamp]
            if not all(t in fed.index and pd.notna(fed[t]) for t in range(1, 31)):
                raise ValueError("Incomplete 1Y-30Y Fed fitted curve.")
            zero = {t: float(fed[t]) for t in range(1, 31)}
            daily: list[dict] = []
            for tenor, note in selected.items():
                price = by_day[day].get(note.cusip)
                if price is None:
                    raise ValueError(f"No FedInvest reference for selected {tenor}Y CUSIP {note.cusip}.")
                market_ref = price.reference_mid_per_100
                ytm = ytm_from_clean(note, day, market_ref)
                dv01 = bond_dv01_per_100(note, day, ytm)
                modeled = price_from_zero_curve(note, day, zero)
                daily.append({
                    "date": day.isoformat(), "tenor": tenor, "cusip": note.cusip,
                    "years_remaining": (note.maturity_date-day).days/365.25,
                    "ref_buy_per_100": price.reference_buy_per_100,
                    "ref_sell_per_100": price.reference_sell_per_100,
                    "ref_mid_per_100": market_ref,
                    "ref_half_spread_per_100": price.indicative_half_spread_per_100,
                    "fitted_model_clean_per_100": modeled,
                    "model_minus_ref_per_100": modeled-market_ref,
                    "model_minus_ref_bp_dv01": (modeled-market_ref)/dv01,
                    "dv01_dollars_per_100_par": dv01,
                    "price_type": "GOVERNMENT_ACCOUNT_REFERENCE_NOT_EXECUTABLE",
                    "source_url": price.source_url,
                    "asof_alignment": "same_date_different_valuation_times_unverified",
                })
            rows.extend(daily)  # append only complete 3-leg dates
        except (ValueError, KeyError) as exc:
            omissions.append({"date": day.isoformat(), "reason": str(exc)})
    return pd.DataFrame(rows), pd.DataFrame(omissions)
