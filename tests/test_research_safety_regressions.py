"""Regression tests for non-trading guards and sub-threshold positioning."""
import numpy as np
import pandas as pd
import pytest

from src.research.signal_engine import generate_signals
from src.trading.instrument_mapper import map_instruments
from src.trading.risk_checks import run_risk_checks


def test_subthreshold_target_is_zero():
    idx = pd.date_range("2025-01-01", periods=10, freq="B")
    s = pd.Series([0, 1, -1, 0, 1, -1, 0, 1, -1, 0], index=idx, dtype=float)
    w = pd.DataFrame({"5": -0.5, "7": 1.0, "10": -0.5}, index=idx)
    result = generate_signals(s, w, entry_z=2.5, signal_cap=3, rolling_window=5).frame
    assert result.iloc[-1]["trade_direction"] == "flat"
    assert result.iloc[-1]["clipped_signal"] == 0


def test_not_enough_history_produces_zero_exposure():
    idx = pd.date_range("2025-01-01", periods=3, freq="B")
    s = pd.Series([1, 2, 3], index=idx, dtype=float)
    w = pd.DataFrame({"5": -0.5, "7": 1., "10": -0.5}, index=idx)
    result = generate_signals(s, w, 2.5, 3, 5).frame
    assert result["clipped_signal"].eq(0).all()


def test_etf_proxy_unpriced_dv01_is_blocked():
    with pytest.raises(NotImplementedError, match="DV01 calibration"):
        map_instruments({5: 10., 7: -15., 10: 5.}, "etf_proxy", {5: "IEF", 7: "IEF", 10: "TLT"})


def test_missing_market_spread_blocks_execution():
    t = pd.Timestamp("2025-01-15")
    check = run_risk_checks(
        latest_curve_date=t, signal_date=t, missing_tenors=[],
        z_score=3.0, entry_z=2.5,
        gross_dv01=100, max_gross_dv01=500,
        leg_exposures={5: -25, 7: 50, 10: -25},
        max_leg_dv01=250, max_position_change=250, order_sizes=[],
        allow_trading=True, paper_trading=True, live_trading=False,
        bid_ask_bps=None, max_bid_ask_bps=2,
        daily_loss=0, max_daily_loss=200, data_fresh=True,
    )
    assert check.passed is False
    assert not next(c for c in check.checks if c["check"] == "bid_ask")["passed"]
