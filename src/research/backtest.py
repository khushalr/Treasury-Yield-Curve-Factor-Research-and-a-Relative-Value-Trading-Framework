"""Causal, illustrative yield-curve backtest; NOT executable bond performance.

Signal at date t is assumed observable only after the daily Fed curve is published.
We delay execution by two daily observations before applying positions to subsequent
close-to-close yield changes. DV01 and transaction cost assumptions are stylized.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.research.fly_model import build_fly_series
from src.research.pca_model import compute_yield_changes, fit_rolling_pca
from src.research.signal_engine import generate_signals
from src.trading.position_sizer import size_target_positions


@dataclass(slots=True)
class BacktestResult:
    daily: pd.DataFrame
    summary: dict[str, float | int | str | None]


def run_walk_forward_backtest(
    curve: pd.DataFrame,
    *,
    tenors: tuple[int, int, int] = (5, 7, 10),
    pca_window: int = 126,
    signal_window: int = 63,
    entry_z: float = 2.5,
    signal_cap: float = 3.0,
    cost_bp: float = 0.5,
    execution_lag: int = 2,
    target_daily_vol: float = 0.01,
    max_gross_dv01: float = 500.0,
    max_leg_dv01: float = 250.0,
) -> BacktestResult:
    """Evaluate synthetic next-session exposures under explicit execution assumptions.

    Input yields are in percentage points (e.g. 4.25 means 4.25%). Each
    exposure is a hypothetical dollar DV01 ($ per 1bp yield change).
    Gross P&L_t = -sum_i(DV01_{i,t-lag} * change_in_yield_bp_{i,t}).
    Transaction costs = cost_bp * gross dollar-DV01 turnover. This is NOT a
    tradable return: no bonds, financing, funding, roll, carry or price quotes.

    Lag 2 is conservative relative to same-close fills: a signal computed from
    a published close on t is not assumed held during the t-to-(t+1) interval.
    """
    if cost_bp < 0 or not np.isfinite(cost_bp):
        raise ValueError("cost_bp must be non-negative and finite.")
    if execution_lag < 2:
        raise ValueError("execution_lag must be at least 2 observations.")
    if pca_window < 10 or signal_window < 5:
        raise ValueError("Rolling windows are too short for meaningful estimates.")
    if curve.empty or not curve.index.is_unique or not curve.index.is_monotonic_increasing:
        raise ValueError("Curve must be nonempty and strictly date-ordered without duplicates.")
    if len(tenors) != 3 or not all(t in curve.columns for t in tenors):
        raise ValueError("All three butterfly tenors must exist in the input.")

    changes = compute_yield_changes(curve)
    pca = fit_rolling_pca(changes, pca_window)
    fly = build_fly_series(changes, pca.loadings, list(tenors))
    signals = generate_signals(
        fly.residual, fly.weights, entry_z, signal_cap, signal_window
    ).frame

    # The rolling volatility estimate never includes today's observed fly move.
    vol = fly.residual.shift(1).rolling(63, min_periods=20).std(ddof=0)
    targets: list[dict[int, float]] = []
    for dt, row in signals.iterrows():
        weights = {t: float(row[f"w_{t}"]) for t in tenors}
        sizing = size_target_positions(
            float(row["target_signal"]), weights, float(vol.loc[dt]),
            target_daily_vol, max_gross_dv01, max_leg_dv01
        )
        targets.append(sizing.target_exposures)

    target = pd.DataFrame(targets, index=signals.index)[list(tenors)]
    # An order decision based on today's published observation cannot earn
    # today's yield move. Two observations is deliberately conservative.
    held = target.shift(execution_lag).fillna(0.0)
    delta_bp = changes.reindex(held.index)[list(tenors)] * 100.0
    gross_pnl = -(held * delta_bp).sum(axis=1)
    turnover = held.diff().fillna(held).abs().sum(axis=1)
    costs = turnover * cost_bp
    net_pnl = gross_pnl - costs
    running = net_pnl.cumsum()
    drawdown = running - running.cummax().clip(lower=0.0)
    std = float(net_pnl.std(ddof=1))
    sharpe = float(np.sqrt(252) * net_pnl.mean() / std) if std > 0 and np.isfinite(std) else None

    daily = pd.DataFrame({
        "z_score": signals["z_score"],
        "target_signal": signals["target_signal"],
        "gross_pnl_usd": gross_pnl,
        "turnover_dv01": turnover,
        "cost_usd": costs,
        "net_pnl_usd": net_pnl,
        "cum_net_pnl_usd": running,
    })
    for t in tenors:
        daily[f"target_dv01_{t}y"] = target[t]
        daily[f"held_dv01_{t}y"] = held[t]
    summary: dict[str, float | int | str | None] = {
        "first_date": str(daily.index.min().date()),
        "last_date": str(daily.index.max().date()),
        "observations": len(daily),
        "active_held_days": int((held.abs().sum(axis=1) > 0).sum()),
        "gross_pnl_usd": float(gross_pnl.sum()),
        "cost_usd": float(costs.sum()),
        "net_pnl_usd": float(net_pnl.sum()),
        "total_turnover_dv01": float(turnover.sum()),
        "annualized_sharpe_illustrative": sharpe,
        "max_drawdown_usd": float(drawdown.min()),
        "cost_bp_per_dv01_turnover": float(cost_bp),
        "execution_lag_observations": execution_lag,
        "disclaimer": "Synthetic DV01 sensitivity, not realized/quoted instrument P&L.",
    }
    return BacktestResult(daily=daily, summary=summary)
