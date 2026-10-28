from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.research.backtest import run_walk_forward_backtest

TENORS = [1, 2, 3, 5, 7, 10, 20, 30]


def _curve() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2023-01-02", periods=145)
    common = rng.normal(0, 0.012, (len(dates), 3))
    loadings = np.stack([
        np.ones(8),
        np.linspace(-1, 1, 8),
        np.array([-1, -0.5, 0, 1, 1.3, 0.9, -0.5, -1]),
    ], axis=0)
    changes = common @ loadings + rng.normal(0, 0.002, (len(dates), 8))
    values = 3.2 + np.cumsum(changes, axis=0)
    return pd.DataFrame(values, index=dates, columns=TENORS)


def test_backtest_costs_never_improve_net_pnl() -> None:
    kwargs = dict(pca_window=35, signal_window=12, entry_z=0.5)
    no_cost = run_walk_forward_backtest(_curve(), cost_bp=0.0, **kwargs)
    costed = run_walk_forward_backtest(_curve(), cost_bp=2.0, **kwargs)
    assert (costed.daily["net_pnl_usd"] <= no_cost.daily["net_pnl_usd"] + 1e-12).all()
    assert costed.summary["cost_usd"] >= 0
    assert costed.summary["observations"] > 50


def test_future_data_cannot_change_prior_backtest() -> None:
    original = _curve()
    disturbed = original.copy()
    disturbed.iloc[-1, :] += 20.0
    opts = dict(pca_window=35, signal_window=12, entry_z=0.5)
    a = run_walk_forward_backtest(original, **opts).daily
    b = run_walk_forward_backtest(disturbed, **opts).daily
    pd.testing.assert_frame_equal(a.iloc[:-1], b.iloc[:-1])


def test_execution_has_two_observation_lag() -> None:
    frame = run_walk_forward_backtest(
        _curve(), pca_window=35, signal_window=12, entry_z=0.5
    ).daily
    for t in (5, 7, 10):
        pd.testing.assert_series_equal(
            frame[f"held_dv01_{t}y"],
            frame[f"target_dv01_{t}y"].shift(2).fillna(0.0),
            check_names=False,
        )


def test_rejects_impossible_execution_lag() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        run_walk_forward_backtest(_curve(), execution_lag=1)
