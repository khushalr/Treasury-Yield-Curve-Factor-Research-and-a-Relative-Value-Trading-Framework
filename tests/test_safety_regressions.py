from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.research.fly_model import _solve_pc_neutral_weights
from src.research.signal_engine import generate_signals
from src.trading.order_builder import build_order_tickets
from src.trading.position_sizer import size_target_positions


def test_flat_signal_has_zero_exposure() -> None:
    days = pd.bdate_range("2025-01-01", periods=12)
    fly = pd.Series(np.sin(np.linspace(0, 2, 12)), index=days)
    weights = pd.DataFrame({"5": -1.0, "7": 1.0, "10": 0.0}, index=days)
    signals = generate_signals(fly, weights, entry_z=999, signal_cap=3,
                               rolling_window=5).frame
    assert (signals["target_signal"] == 0).all()
    assert (signals["trade_direction"] == "flat").all()


def test_sizer_preserves_fly_ratios_under_leg_cap() -> None:
    result = size_target_positions(
        signal_strength=-3, fly_weights={5: -1, 7: 1, 10: -1},
        residual_vol=0.01, target_daily_vol=0.02,
        max_gross_dv01=3000, max_leg_dv01=100
    )
    v = result.target_exposures
    assert v[5] == pytest.approx(-100)
    assert v[7] == pytest.approx(100)
    assert v[10] == pytest.approx(-100)
    assert result.gross_dv01 == pytest.approx(300)


def test_sizer_invalid_vol_returns_flat() -> None:
    result = size_target_positions(
        signal_strength=2, fly_weights={5: -0.5, 7: 1, 10: -0.5},
        residual_vol=float("nan"), target_daily_vol=0.01,
        max_gross_dv01=500, max_leg_dv01=250
    )
    assert result.gross_dv01 == 0


def test_ill_conditioned_hedge_rejected() -> None:
    loadings = pd.DataFrame({"PC1": [1.0, 1.0, 1.0],
                             "PC2": [1.0, 1.0, 1.0]}, index=[5, 7, 10])
    with pytest.raises(ValueError, match="Ill-conditioned"):
        _solve_pc_neutral_weights(loadings, [5, 7, 10])


def test_non_dry_run_order_builder_is_blocked() -> None:
    with pytest.raises(ValueError, match="research-only"):
        build_order_tickets({"IEF": 4}, {}, "2025-01-01", dry_run=False)
