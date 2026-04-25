"""Trading risk checks that gate any order submission."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class RiskCheckResult:
    passed: bool
    checks: list[dict[str, str | bool]]


def _record(checks: list[dict[str, str | bool]], name: str, passed: bool, msg: str) -> None:
    checks.append({"check": name, "passed": passed, "message": msg})


def run_risk_checks(
    *,
    latest_curve_date: pd.Timestamp,
    signal_date: pd.Timestamp,
    missing_tenors: list[int],
    z_score: float,
    entry_z: float,
    gross_dv01: float,
    max_gross_dv01: float,
    leg_exposures: dict[int, float],
    max_leg_dv01: float,
    max_position_change: float,
    order_sizes: list[float],
    allow_trading: bool,
    paper_trading: bool,
    live_trading: bool,
    bid_ask_bps: float | None,
    max_bid_ask_bps: float,
    daily_loss: float,
    max_daily_loss: float,
    data_fresh: bool,
) -> RiskCheckResult:
    """Run pre-trade checks and return explicit pass/fail reasons."""

    checks: list[dict[str, str | bool]] = []
    _record(checks, "data_fresh", data_fresh, "Curve data freshness check.")
    _record(checks, "signal_latest", signal_date == latest_curve_date, "Signal date must match latest curve date.")
    _record(checks, "missing_tenors", len(missing_tenors) == 0, f"Missing tenors: {missing_tenors}")
    _record(checks, "entry_threshold", abs(z_score) >= entry_z, f"|z|={abs(z_score):.2f}, entry={entry_z:.2f}")
    _record(checks, "gross_dv01_cap", gross_dv01 <= max_gross_dv01, f"gross={gross_dv01:.2f}, cap={max_gross_dv01:.2f}")

    legs_ok = all(abs(v) <= max_leg_dv01 for v in leg_exposures.values())
    _record(checks, "leg_dv01_cap", legs_ok, "Each leg exposure must be under cap.")

    orders_ok = all(abs(v) <= max_position_change for v in order_sizes)
    _record(checks, "order_size_cap", orders_ok, "Order sizes must be under max position change.")

    _record(checks, "allow_trading", allow_trading, "ALLOW_TRADING must be true for execution.")
    _record(checks, "paper_only", paper_trading and not live_trading, "Execution must remain paper-only.")

    spread_ok = True if bid_ask_bps is None else bid_ask_bps <= max_bid_ask_bps
    _record(checks, "bid_ask", spread_ok, "Bid/ask spread check when market data is available.")
    _record(checks, "daily_loss", daily_loss <= max_daily_loss, "Daily loss limit check.")

    passed = all(bool(c["passed"]) for c in checks)
    return RiskCheckResult(passed=passed, checks=checks)
