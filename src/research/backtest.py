"""Point-in-time synthetic Treasury butterfly backtest (not executable bond P&L).

Signals are computed after each curve observation. The resulting position earns
its first mark-to-market P&L on the *next* observation. Prices are approximated
from parallel per-tenor yield changes and fixed $1/bp gross DV01; no capital
return, carry, financing, convexity, or cash security execution is modelled.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.research.fly_model import build_fly_series
from src.research.pca_model import compute_yield_changes, fit_rolling_pca


@dataclass(frozen=True)
class BacktestConfig:
    pca_window: int = 504
    z_window: int = 126
    entry_z: float = 2.5
    exit_z: float = 0.5
    # Assumed ONE-WAY execution cost: bp of yield times $1/bp DV01 traded.
    cost_yield_bp: float = 0.25
    max_abs_raw_weight: float = 20.0
    tenors: tuple[int, int, int] = (5, 7, 10)
    holdout_fraction: float = 0.30


@dataclass
class BacktestResult:
    daily: pd.DataFrame
    summary: dict[str, float | int | str | None]


def _sharpe_of_unit_pnl(values: pd.Series) -> float | None:
    """Annualized t-stat-like Sharpe of synthetic unit-DV01 P&L, NOT ROI."""
    clean = values.dropna()
    if len(clean) < 2 or clean.std(ddof=1) <= 0:
        return None
    return float(np.sqrt(252) * clean.mean() / clean.std(ddof=1))


def _metrics(frame: pd.DataFrame, prefix: str = "") -> dict[str, float | int | str | None]:
    net = frame["net_pnl_per_unit_dv01"]
    return {
        f"{prefix}observations": int(len(frame)),
        f"{prefix}gross_pnl_per_unit_dv01": float(frame["gross_pnl_per_unit_dv01"].sum()),
        f"{prefix}cost_per_unit_dv01": float(frame["cost_per_unit_dv01"].sum()),
        f"{prefix}net_pnl_per_unit_dv01": float(net.sum()),
        f"{prefix}turnover_unit_dv01": float(frame["turnover_unit_dv01"].sum()),
        f"{prefix}entries": int(frame["new_entry"].sum()),
        f"{prefix}unit_pnl_sharpe_not_roi": _sharpe_of_unit_pnl(net),
    }


def run_synthetic_backtest(curve: pd.DataFrame, config: BacktestConfig | None = None) -> BacktestResult:
    """Backtest a point-in-time 5Y/7Y/10Y level-spread mean reversion rule.

    PCA is calibrated on YIELD CHANGES up to t-1. The value at t and its prior
    z-window observations are projected on the SAME t-specific fly weights,
    avoiding a spurious signal from historical changes in hedge weights.

    Positive z = unusually HIGH belly-minus-wings *yield* = LONG belly DV01
    (buy cheap belly), SHORT wing DV01; the opposite for negative z.
    Mark-to-market P&L from t-1 close exposure is -sum(DV01 * delta_yield_bp).

    Entire strategy is a synthetic scenario; signal dates are research-date
    labels, not tradable execution timestamps. Cost assumptions are illustrative.
    """
    cfg = config or BacktestConfig()
    if (cfg.pca_window < 3 or cfg.z_window < 3 or cfg.entry_z <= 0
            or cfg.exit_z < 0 or cfg.exit_z >= cfg.entry_z
            or cfg.cost_yield_bp < 0 or cfg.max_abs_raw_weight <= 0
            or not 0 < cfg.holdout_fraction < 1):
        raise ValueError("Invalid backtest parameters.")
    tenors = list(cfg.tenors)
    if len(tenors) != 3 or len(set(tenors)) != 3:
        raise ValueError("Specify three distinct ordered tenors (wing, belly, wing).")
    if any(t not in curve.columns for t in tenors):
        raise ValueError("Missing required yield tenor columns.")
    if (not isinstance(curve.index, pd.DatetimeIndex)
            or not curve.index.is_monotonic_increasing or not curve.index.is_unique):
        raise ValueError("Curve requires unique, ascending DatetimeIndex.")
    values = curve.loc[:, tenors].astype(float)
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError("Missing/invalid yields: clean data explicitly before backtesting.")
    if len(values) <= cfg.pca_window + cfg.z_window + 2:
        raise ValueError("Insufficient curve history for PCA and prior z-score window.")

    changes = compute_yield_changes(values)
    rolling = fit_rolling_pca(changes, window=cfg.pca_window, n_components=3)
    fly = build_fly_series(changes, rolling.loadings, tenors)
    raw_weights = fly.weights.reindex(values.index)
    dates = values.index
    held = np.zeros(3, dtype=float)
    state = 0
    previous_yields = None
    output: list[dict[str, object]] = []

    for idx, dt in enumerate(dates):
        today = values.loc[dt, tenors].to_numpy(dtype=float)
        pnl = float(-np.dot(held, (today - previous_yields) * 100)) if previous_yields is not None else 0.0
        weights = raw_weights.loc[dt].to_numpy(dtype=float)
        z = float("nan")
        target = np.zeros(3, dtype=float)
        next_state = 0
        if (idx >= cfg.z_window and np.isfinite(weights).all()
                and max(abs(weights)) <= cfg.max_abs_raw_weight
                and weights[0] < 0 and weights[1] > 0 and weights[2] < 0):
            weights = weights / np.abs(weights).sum()  # $1/bp gross DV01
            # Historical fly levels are evaluated using *today's* known weights.
            history = values.iloc[idx - cfg.z_window:idx][tenors].to_numpy() @ weights
            s = float(np.std(history, ddof=0))
            if s > 1e-10:
                z = float((today @ weights - history.mean()) / s)
                if state == 0:
                    next_state = 1 if z >= cfg.entry_z else (-1 if z <= -cfg.entry_z else 0)
                elif state > 0:
                    next_state = 0 if z <= cfg.exit_z else 1
                else:
                    next_state = 0 if z >= -cfg.exit_z else -1
                target = next_state * weights

        turnover = float(np.abs(target - held).sum())
        cost = cfg.cost_yield_bp * turnover
        output.append({
            "date": dt,
            "z_score": z,
            "position_at_close": next_state,
            "new_entry": bool(state == 0 and next_state != 0),
            "loading_date_used": fly.loading_date_used.get(dt, pd.NaT),
            "exposure_5": float(target[0]),
            "exposure_7": float(target[1]),
            "exposure_10": float(target[2]),
            "gross_pnl_per_unit_dv01": pnl,
            "turnover_unit_dv01": turnover,
            "cost_per_unit_dv01": cost,
            "net_pnl_per_unit_dv01": pnl - cost,
        })
        held = target
        state = next_state
        previous_yields = today

    daily = pd.DataFrame(output).set_index("date")
    # Chronological reporting split only. Not an untouched OOS result when model
    # choices were tuned on this same dataset.
    split = int(len(daily) * (1 - cfg.holdout_fraction))
    holdout = daily.iloc[split:]
    summary = {
        "methodology": "synthetic $1/bp gross-DV01, close-to-close yield-change approximation",
        "cost_yield_bp_each_way": cfg.cost_yield_bp,
        "holdout_start_date": str(holdout.index[0].date()),
        "holdout_warning": "Chronological split; not a true untouched test if parameters were selected on full sample.",
        **_metrics(daily),
        **_metrics(holdout, prefix="holdout_"),
    }
    return BacktestResult(daily=daily, summary=summary)
