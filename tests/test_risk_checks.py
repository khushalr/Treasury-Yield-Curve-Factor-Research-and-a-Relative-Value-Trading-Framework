from __future__ import annotations

import pandas as pd

from src.trading.ibkr_client import IBKRSafetyFlags, can_submit_order
from src.trading.risk_checks import run_risk_checks


def _base_kwargs() -> dict:
    dt = pd.Timestamp("2025-01-15")
    return dict(
        latest_curve_date=dt,
        signal_date=dt,
        missing_tenors=[],
        z_score=3.0,
        entry_z=2.5,
        gross_dv01=100.0,
        max_gross_dv01=500.0,
        leg_exposures={5: 30.0, 7: -50.0, 10: 20.0},
        max_leg_dv01=250.0,
        max_position_change=250.0,
        order_sizes=[10.0],
        allow_trading=True,
        paper_trading=True,
        live_trading=False,
        bid_ask_bps=1.0,
        max_bid_ask_bps=2.0,
        daily_loss=0.0,
        max_daily_loss=200.0,
        data_fresh=True,
    )


def test_block_when_allow_trading_false() -> None:
    kwargs = _base_kwargs()
    kwargs["allow_trading"] = False
    result = run_risk_checks(**kwargs)
    assert not result.passed


def test_block_when_live_trading_true() -> None:
    kwargs = _base_kwargs()
    kwargs["live_trading"] = True
    result = run_risk_checks(**kwargs)
    assert not result.passed


def test_block_when_data_stale_or_missing() -> None:
    kwargs = _base_kwargs()
    kwargs["data_fresh"] = False
    kwargs["missing_tenors"] = [7]
    result = run_risk_checks(**kwargs)
    assert not result.passed


def test_submit_blocked_for_live_even_if_other_flags_true() -> None:
    safety = IBKRSafetyFlags(dry_run=False, allow_trading=True, paper_trading=True, live_trading=True)
    ok, reason = can_submit_order(safety, risk_passed=True)
    assert not ok
    assert "LIVE_TRADING" in reason
