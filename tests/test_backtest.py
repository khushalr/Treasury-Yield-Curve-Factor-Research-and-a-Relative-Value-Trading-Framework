"""Synthetic-data regression tests for research backtesting, not trading."""
import numpy as np
import pandas as pd
import pytest

from src.research.backtest import BacktestConfig, run_synthetic_backtest


def curve(n=110, seed=7):
    rng = np.random.default_rng(seed)
    level = rng.normal(0, 0.035, n)
    slope = rng.normal(0, 0.015, n)
    bend = rng.normal(0, 0.003, n)
    shocks = level[:, None] + slope[:, None] * np.array([-1, 0, 1]) + bend[:, None] * np.array([-1, 2, -1])
    return pd.DataFrame(np.cumsum(shocks, axis=0) + [3, 3.2, 3.4], columns=[5, 7, 10], index=pd.bdate_range('2023-01-02', periods=n))


def settings(**kw):
    return BacktestConfig(pca_window=20, z_window=15, entry_z=1.2, exit_z=.25, **kw)


def test_backtest_accounting_and_one_observation_execution_lag():
    c = curve()
    r = run_synthetic_backtest(c, settings(cost_yield_bp=.2))
    assert r.summary['observations'] > 0
    d = r.daily
    assert (d['executed_gross_dv01'] <= 1.00000001).all()
    assert (d['cost_per_unit_dv01'] >= 0).all()
    np.testing.assert_allclose(d['net_pnl_per_unit_dv01'], d['gross_pnl_per_unit_dv01']-d['cost_per_unit_dv01'])
    np.testing.assert_allclose(d['executed_gross_dv01'], d[['executed_5','executed_7','executed_10']].abs().sum(axis=1))
    idx = d.index[d['executed_gross_dv01'] > .5]
    assert len(idx) > 0
    dt = idx[0]
    i = c.index.get_loc(dt)
    np.testing.assert_allclose(
        d.iloc[i+1]['gross_pnl_per_unit_dv01'],
        -float(d.iloc[i][['executed_5','executed_7','executed_10']].to_numpy(dtype=float) @ ((c.iloc[i+1]-c.iloc[i]).to_numpy()*100))
    )


def test_no_future_yields_affect_prior_decisions_or_returns():
    c = curve()
    a = run_synthetic_backtest(c, settings()).daily
    c2 = c.copy()
    c2.loc[c2.index[86]:, 7] += 20
    b = run_synthetic_backtest(c2, settings()).daily
    pd.testing.assert_frame_equal(a.iloc[:86], b.iloc[:86])


def test_higher_costs_never_improve_net_pnl():
    c = curve()
    cheap = run_synthetic_backtest(c, settings(cost_yield_bp=0)).daily
    costly = run_synthetic_backtest(c, settings(cost_yield_bp=2)).daily
    pd.testing.assert_series_equal(cheap['gross_pnl_per_unit_dv01'], costly['gross_pnl_per_unit_dv01'])
    assert costly['net_pnl_per_unit_dv01'].sum() <= cheap['net_pnl_per_unit_dv01'].sum()


def test_bad_input_fails_before_fitting():
    c = curve()
    c.iloc[30, 1] = np.nan
    with pytest.raises(ValueError, match='Nonfinite'):
        run_synthetic_backtest(c, settings())
    with pytest.raises(ValueError, match='index'):
        run_synthetic_backtest(curve().iloc[::-1], settings())
    with pytest.raises(ValueError, match='configuration'):
        run_synthetic_backtest(curve(), settings(cost_yield_bp=-.1))
