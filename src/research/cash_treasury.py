"""Research-only cash Treasury CUSIP selection, pricing and DV01 sizing.

Auction metadata is NOT a quote; requires externally sourced same-date bid/ask
clean prices. No broker connectivity or executable order creation.
"""
from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class TreasuryNote:
    cusip: str
    issue_date: date
    maturity_date: date
    coupon_percent: float
    original_term: str


@dataclass(frozen=True)
class BondQuote:
    cusip: str
    as_of: date
    bid_clean: float
    ask_clean: float
    source: str

    @property
    def mid_clean(self) -> float:
        return (self.bid_clean + self.ask_clean) / 2


@dataclass(frozen=True)
class Valuation:
    note: TreasuryNote
    quote: BondQuote
    remaining_years: float
    model_clean: float
    mid_clean: float
    ytm_percent: float
    dv01_per_100: float
    residual_per_100: float
    residual_bp_dv01: float


def _date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def parse_auction_records(records: Sequence[Mapping[str, object]], as_of: date) -> list[TreasuryNote]:
    """Deduplicate reopenings by CUSIP and reject contradictory metadata."""
    by_cusip: dict[str, TreasuryNote] = {}
    for record in records:
        if str(record.get("security_type", "")).strip() != "Note":
            continue
        cusip = str(record.get("cusip", "")).strip().upper()
        if len(cusip) != 9 or not cusip.isalnum():
            continue
        try:
            issue = _date(str(record["issue_date"]))
            maturity = _date(str(record["maturity_date"]))
            auction = _date(str(record["auction_date"]))
            coupon = float(record["int_rate"])
        except (KeyError, ValueError, TypeError):
            continue
        if not (issue <= as_of and auction <= as_of and maturity > as_of):
            continue
        if not (0 < coupon < 25 and issue < maturity):
            continue
        current = TreasuryNote(cusip, issue, maturity, coupon, str(record.get("security_term", "")))
        prior = by_cusip.get(cusip)
        if prior is not None:
            if prior.maturity_date != maturity or abs(prior.coupon_percent - coupon) > 1e-8:
                raise ValueError(f"Conflicting Treasury security records for CUSIP {cusip}.")
            if current.issue_date < prior.issue_date:
                by_cusip[cusip] = current
        else:
            by_cusip[cusip] = current
    return list(by_cusip.values())


def select_cash_notes(
    universe: Sequence[TreasuryNote], as_of: date,
    tenors: Sequence[int] = (5, 7, 10), minimum_age_days: int = 90,
    maximum_maturity_gap_years: float = 0.85,
) -> dict[int, TreasuryNote]:
    """Closest *remaining*-maturity, seasoned, distinct note CUSIPs."""
    if len(set(tenors)) != len(tenors) or minimum_age_days < 0 or maximum_maturity_gap_years <= 0:
        raise ValueError("Invalid CUSIP-selection constraints.")
    eligible = [n for n in universe if n.issue_date <= as_of and n.maturity_date > as_of
                and (as_of - n.issue_date).days >= minimum_age_days]
    chosen: dict[int, TreasuryNote] = {}
    used: set[str] = set()
    for tenor in tenors:
        candidates = sorted((n for n in eligible if n.cusip not in used),
                            key=lambda n: (abs((n.maturity_date-as_of).days / 365.25-tenor), n.cusip))
        if not candidates:
            raise ValueError(f"No eligible cash Treasury near {tenor}Y.")
        best = candidates[0]
        if abs((best.maturity_date-as_of).days/365.25-tenor) > maximum_maturity_gap_years:
            raise ValueError(f"Nearest {tenor}Y security falls outside the maturity tolerance.")
        chosen[int(tenor)] = best
        used.add(best.cusip)
    return chosen


def _shift_months(anchor: date, months: int) -> date:
    year = anchor.year + (anchor.month - 1 + months)//12
    month = (anchor.month - 1 + months)%12 + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def coupon_schedule(note: TreasuryNote, as_of: date) -> tuple[list[tuple[date, float]], float, float]:
    """Semiannual cash flows, approximate ACT/ACT accrued interest and stub fraction."""
    if not note.issue_date <= as_of < note.maturity_date:
        raise ValueError("Note is unissued or matured on as-of date.")
    dates = []
    for periods in range(101):
        d = _shift_months(note.maturity_date, -6 * periods)
        if d <= as_of:
            previous_coupon = d
            break
        dates.append(d)
    else:
        raise ValueError("Unbounded coupon schedule.")
    dates.reverse()
    next_coupon = dates[0]
    fraction = (next_coupon-as_of).days / (next_coupon-previous_coupon).days
    accrued = note.coupon_percent / 2 * (as_of-previous_coupon).days/(next_coupon-previous_coupon).days
    cashflows = [(d, note.coupon_percent/2 + (100 if d == note.maturity_date else 0)) for d in dates]
    return cashflows, accrued, fraction


def clean_price_from_ytm(note: TreasuryNote, as_of: date, ytm_percent: float) -> float:
    payments, accrued, fraction = coupon_schedule(note, as_of)
    base = 1 + ytm_percent / 200
    if base <= 0:
        raise ValueError("Invalid bond-equivalent yield.")
    dirty = sum(amount * base ** (-2 * (fraction + k)) for k, (_, amount) in enumerate(payments))
    return dirty - accrued


def ytm_from_clean(note: TreasuryNote, as_of: date, price: float) -> float:
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Clean price must be finite and positive.")
    lo, hi = -199.0, 150.0
    if not (clean_price_from_ytm(note, as_of, lo) >= price >= clean_price_from_ytm(note, as_of, hi)):
        raise ValueError("Price outside supported bond-yield range.")
    for _ in range(110):
        mid = (lo+hi)/2
        if clean_price_from_ytm(note, as_of, mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def bond_dv01_per_100(note: TreasuryNote, as_of: date, ytm_percent: float) -> float:
    dv01 = (clean_price_from_ytm(note, as_of, ytm_percent-.01) -
            clean_price_from_ytm(note, as_of, ytm_percent+.01))/2
    if not math.isfinite(dv01) or dv01 <= 0:
        raise ValueError("Nonpositive dollar DV01.")
    return dv01


def price_from_zero_curve(
    note: TreasuryNote, as_of: date, fitted_zero_yields_percent: Mapping[int, float],
) -> float:
    """Indicative clean price from linearly interpolated fitted continuous zero rates.

    Simplifying assumption: shorter than 1Y uses the 1Y fitted rate flat.
    This is an approximation, NOT an arbitrage-free live executable mark.
    """
    tenors = sorted(fitted_zero_yields_percent)
    if not tenors or tenors[0] > 1 or tenors[-1] < 11:
        raise ValueError("Require 1Y through at least 11Y fitted zero yields.")
    rates = np.array([float(fitted_zero_yields_percent[x]) for x in tenors])
    if not np.isfinite(rates).all():
        raise ValueError("Nonfinite zero-curve yields.")
    payments, accrued, _ = coupon_schedule(note, as_of)
    dirty = 0.0
    for d, amount in payments:
        years = (d-as_of).days/365.25
        if years > tenors[-1]:
            raise ValueError("Fitted curve too short for this note.")
        continuous_yield_percent = float(np.interp(years, tenors, rates))
        dirty += amount * math.exp(-continuous_yield_percent/100 * years)
    return dirty - accrued


def read_quotes(path: Path, as_of: date) -> dict[str, BondQuote]:
    """Fail closed without attributable bid AND ask prices on exact as-of date."""
    quotes: dict[str, BondQuote] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"as_of", "cusip", "bid_clean", "ask_clean", "source"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Quote CSV missing columns: {sorted(required-set(reader.fieldnames or []))}")
        for row in reader:
            quote = BondQuote(str(row["cusip"]).strip().upper(), _date(row["as_of"]),
                              float(row["bid_clean"]), float(row["ask_clean"]), str(row["source"]).strip())
            if quote.as_of != as_of:
                raise ValueError("Quote date does not match as-of date.")
            if (not math.isfinite(quote.bid_clean) or not math.isfinite(quote.ask_clean)
                    or quote.bid_clean <= 0 or quote.ask_clean < quote.bid_clean
                    or not quote.source or quote.source.lower() in {"unknown", "none", "synthetic"}):
                raise ValueError("Invalid or unattributed bid/ask quote.")
            if quote.cusip in quotes:
                raise ValueError(f"Duplicate quote for {quote.cusip}.")
            quotes[quote.cusip] = quote
    return quotes


def value_notes(selected: Mapping[int, TreasuryNote], quotes: Mapping[str, BondQuote],
                as_of: date, fitted_zero_yields_percent: Mapping[int, float]) -> dict[int, Valuation]:
    result = {}
    for tenor, note in selected.items():
        if note.cusip not in quotes:
            raise ValueError(f"Missing exact-date bid/ask quotes for {note.cusip} ({tenor}Y).")
        quote = quotes[note.cusip]
        if quote.as_of != as_of:
            raise ValueError("Quote date mismatch.")
        ytm = ytm_from_clean(note, as_of, quote.mid_clean)
        dv01 = bond_dv01_per_100(note, as_of, ytm)
        fair = price_from_zero_curve(note, as_of, fitted_zero_yields_percent)
        gap = fair-quote.mid_clean
        result[tenor] = Valuation(note, quote, (note.maturity_date-as_of).days/365.25,
                                  fair, quote.mid_clean, ytm, dv01, gap, gap/dv01)
    return result


def construct_paper_fly(valuations: Mapping[int, Valuation], direction: int,
                        gross_target_dv01: float, min_face_increment: float = 1000) -> dict[str, object]:
    """Dollar DV01-neutral in level and linear *actual remaining-maturity* slope.

    +1 = BUY belly/SELL wings, -1 reverse, 0 flat.
    Never treats dollars of DV01 as broker-native order quantities.
    """
    if direction not in (-1, 0, 1) or not math.isfinite(gross_target_dv01) or gross_target_dv01 <= 0 or min_face_increment <= 0:
        raise ValueError("Invalid paper signal direction or risk budget.")
    if sorted(valuations) != [5, 7, 10]:
        raise ValueError("Requires 5Y, 7Y and 10Y cash securities.")
    remaining = [valuations[k].remaining_years for k in (5, 7, 10)]
    if not (0 < remaining[0] < remaining[1] < remaining[2]):
        raise ValueError("Inconsistent remaining maturity order.")
    wings = np.linalg.solve(
        np.array([[1., 1.], [remaining[0], remaining[2]]]),
        np.array([-1., -remaining[1]]),
    )
    w = np.array([wings[0], 1., wings[1]])
    w = w/np.abs(w).sum()
    target = {t: float(direction * gross_target_dv01 * x) for t, x in zip((5, 7, 10), w)}
    legs = []
    for tenor, val in sorted(valuations.items()):
        desired = target[tenor]
        face = (round(abs(desired)/val.dv01_per_100*100/min_face_increment)
                * min_face_increment) if desired else 0
        signed_face = math.copysign(face, desired) if desired else 0.
        actual_risk = signed_face/100*val.dv01_per_100
        legs.append({
            "tenor_bucket": tenor, "cusip": val.note.cusip,
            "coupon_percent": val.note.coupon_percent,
            "issue_date": val.note.issue_date.isoformat(),
            "maturity_date": val.note.maturity_date.isoformat(),
            "years_to_maturity": round(val.remaining_years, 4),
            "bid_clean_per_100": val.quote.bid_clean,
            "ask_clean_per_100": val.quote.ask_clean,
            "quote_source": val.quote.source,
            "ytm_percent_mid": round(val.ytm_percent, 6),
            "model_clean_per_100": round(val.model_clean, 6),
            "mid_clean_per_100": val.mid_clean,
            "model_minus_mid_per_100": round(val.residual_per_100, 6),
            "model_minus_mid_bp_of_dv01": round(val.residual_bp_dv01, 4),
            "dv01_per_100_par": round(val.dv01_per_100, 8),
            "target_dv01_dollars_per_bp": round(desired, 3),
            "hypothetical_side": "BUY" if signed_face > 0 else "SELL" if signed_face < 0 else "FLAT",
            "signed_face_usd": signed_face,
            "rounded_dv01_dollars_per_bp": round(actual_risk, 4),
            "half_spread_entry_cost_usd": round(abs(signed_face)/100*
                                                (val.quote.ask_clean-val.quote.bid_clean)/2, 4),
        })
    level = sum(x["rounded_dv01_dollars_per_bp"] for x in legs)
    slope = sum(x["rounded_dv01_dollars_per_bp"]*x["years_to_maturity"] for x in legs)
    entry_spread = sum(x["half_spread_entry_cost_usd"] for x in legs)
    fair_gap = sum(x["signed_face_usd"]/100*x["model_minus_mid_per_100"] for x in legs)
    return {
        "mode": "CASH_TREASURY_RESEARCH_ONLY_NO_ORDER_SUBMISSION",
        "direction": direction,
        "gross_target_dv01_dollars_per_bp": gross_target_dv01,
        "tenor_buckets": [5, 7, 10],
        "legs": legs,
        "rounded_level_dv01_usd_per_bp": round(level, 4),
        "rounded_tenor_weighted_dv01": round(slope, 4),
        "total_half_spread_entry_cost_usd": round(entry_spread, 4),
        "indicative_model_gap_usd_before_financing": round(fair_gap, 4),
        "indicative_model_gap_less_entry_spread_usd": round(fair_gap-entry_spread, 4),
        "caveats": [
            "Illustrative face amounts are NOT broker orders; borrow and financing not verified.",
            "PCA signal has NOT been validated against actual bond excess returns.",
            "Fed zero curve is revised/smoothed and is NOT an executable price.",
            "Semiannual coupons, approximate ACT/ACT accrual, trade-date settlement assumption.",
            "Level/linear remaining-maturity DV01 neutrality, NOT key-rate or PC hedge neutrality.",
            "Estimated entry half-spread omits financing, exit costs, market impact and repo specialness.",
        ],
    }
