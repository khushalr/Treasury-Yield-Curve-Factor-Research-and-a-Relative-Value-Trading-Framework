"""Point-in-time, deliberately SYNTHETIC Treasury butterfly research backtest.

NOT bond/ETF returns: uses duration-linearized yield changes at fixed $1/bp
GROSS DV01. No coupon/carry, roll-down, financing, convexity, repo, or quotes.
Signals from observation t can only be implemented at observation t+1.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    pca_window: int = 504
    z_window: int = 126
    entry_z: float = 2.5
    exit_z: float = 0.5
    cost_yield_bp: float = 0.25  # one-way cost, bp of yield per $/bp DV01 traded
    max_abs_raw_weight: float = 20.0
    tenors: tuple[int, int, int] = (5, 7, 10)
    holdout_fraction: float = 0.30


@dataclass
class BacktestResult:
    daily: pd.DataFrame
    summary: dict[str, float | int | str | None]


def _metrics(frame: pd.DataFrame, prefix: str = "") -> dict[str, float | int | None]:
    pnl = frame["net_pnl_per_unit_dv01"]
    std = float(pnl.std(ddof=1)) if len(pnl) > 1 else 0.0
    return {
        f"{prefix}observations": int(len(frame)),
        f"{prefix}gross_pnl_per_unit_dv01": float(frame["gross_pnl_per_unit_dv01"].sum()),
        f"{prefix}cost_per_unit_dv01": float(frame["cost_per_unit_dv01"].sum()),
        f"{prefix}net_pnl_per_unit_dv01": float(pnl.sum()),
        f"{prefix}turnover_unit_dv01": float(frame["turnover_unit_dv01"].sum()),
        f"{prefix}entries": int(frame["new_entry"].sum()),
        f"{prefix}unit_pnl_sharpe_not_roi": float(np.sqrt(252) * pnl.mean() / std) if std > 0 else None,
    }


def _pca_neutral_weights(hist_changes: np.ndarray, max_abs_weight: float) -> np.ndarray | None:
    """Use the least-variance PCA direction, with +1 belly and negative wings."""
    covariance = np.cov(hist_changes, rowvar=False)
    if not np.isfinite(covariance).all():
        return None
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues[0] <= 0 or eigenvalues[-1] <= 0:
        return None
    normal = eigenvectors[:, 0]  # orthogonal to PC1 and PC2
    if abs(normal[1]) < 1.0 / max_abs_weight:
        return None
    raw = normal / normal[1]
    if (not np.isfinite(raw).all() or np.max(np.abs(raw)) > max_abs_weight
            or raw[0] >= 0 or raw[2] >= 0):
        return None
    return raw / np.abs(raw).sum()


def run_synthetic_backtest(curve: pd.DataFrame, config: BacktestConfig | None = None) -> BacktestResult:
    """Compute delayed-execution synthetic P&L and an explicitly NON-ROI summary.

    At t, weights fit on changes through t-1. They are applied consistently to
    all prior z-window curve levels and today's level; the mean/std exclude t.
    Positive belly-minus-wings yield z -> long belly price DV01 and short wings.
    The decision at t is not filled until t+1, and only affects P&L from t+1
    to t+2. This still assumes unobtainable end-of-day smoothed-curve marks.
    """
    cfg = config or BacktestConfig()
    if (cfg.pca_window < 4 or cfg.z_window < 4 or cfg.entry_z <= 0
            or not 0 <= cfg.exit_z < cfg.entry_z or cfg.cost_yield_bp < 0
            or not np.isfinite(cfg.cost_yield_bp)
            or cfg.max_abs_raw_weight <= 1 or not 0 < cfg.holdout_fraction < 1):
        raise ValueError("Invalid backtest configuration.")
    if len(cfg.tenors) != 3 or tuple(sorted(cfg.tenors)) != cfg.tenors or len(set(cfg.tenors)) != 3:
        raise ValueError("Exactly three increasing (wing, belly, wing) tenors required.")
    if any(t not in curve.columns for t in cfg.tenors):
        raise ValueError("Missing required yield tenor columns.")
    if (not isinstance(curve.index, pd.DatetimeIndex)
            or not curve.index.is_monotonic_increasing or not curve.index.is_unique):
        raise ValueError("The curve index must contain unique, increasing dates.")
    values = curve.loc[:, list(cfg.tenors)].astype(float)
    levels = values.to_numpy()
    if not np.isfinite(levels).all():
        raise ValueError("Nonfinite yields; clean NA observations explicitly first.")
    if len(values) < max(cfg.pca_window + 2, cfg.z_window + 2) + 3:
        raise ValueError("Insufficient yield history for windows and execution lag.")

    changes = np.diff(levels, axis=0)
    active = np.zeros(3)   # exposures EXECUTED at the preceding curve observation
    pending = np.zeros(3)  # decision generated yesterday, to execute today
    decision_side = 0
    output: list[dict[str, object]] = []
    warmup = max(cfg.pca_window + 1, cfg.z_window)

    for i, dt in enumerate(values.index):
        # Mark P&L before trading today using only yesterday's actual exposures.
        gross = float(-active @ ((levels[i] - levels[i - 1]) * 100)) if i else 0.0
        turnover = float(np.abs(pending - active).sum())
        cost = turnover * cfg.cost_yield_bp
        active = pending.copy()  # execute yesterday's intention at today's curve proxy

        # Fit strictly before today's observation; same weights for all z values.
        z = float("nan")
        weights = None
        if i >= warmup:
            hist_changes = changes[i - cfg.pca_window - 1:i - 1]
            weights = _pca_neutral_weights(hist_changes, cfg.max_abs_raw_weight)
            if weights is not None:
                history = levels[i - cfg.z_window:i] @ weights
                historical_std = float(np.std(history, ddof=0))
                if historical_std > 1e-10:
                    z = float(((levels[i] @ weights) - history.mean()) / historical_std)

        next_side = 0
        next_target = np.zeros(3)
        if np.isfinite(z) and weights is not None:
            if decision_side == 0:
                next_side = 1 if z >= cfg.entry_z else -1 if z <= -cfg.entry_z else 0
            elif decision_side > 0:
                next_side = -1 if z <= -cfg.entry_z else 0 if z <= cfg.exit_z else 1
            else:
                next_side = 1 if z >= cfg.entry_z else 0 if z >= -cfg.exit_z else -1
            next_target = next_side * weights

        new_entry = (decision_side == 0 and next_side != 0)
        output.append({
            "date": dt,
            "eligible": i > warmup + 1,
            "z_score": z,
            "decision_side": next_side,
            "executed_gross_dv01": float(np.abs(active).sum()),
            "executed_5": float(active[0]),
            "executed_7": float(active[1]),
            "executed_10": float(active[2]),
            "new_entry": new_entry,
            "gross_pnl_per_unit_dv01": gross,
            "turnover_unit_dv01": turnover,
            "cost_per_unit_dv01": cost,
            "net_pnl_per_unit_dv01": gross - cost,
        })
        decision_side = next_side
        pending = next_target

    daily = pd.DataFrame(output).set_index("date")
    eligible = daily[daily["eligible"]]
    split = max(1, int(len(eligible) * (1 - cfg.holdout_fraction)))
    holdout = eligible.iloc[split:]
    summary = {
        "methodology": "SYNTHETIC $1/bp gross DV01, delayed one observation, no ROI/carry/financing",
        "cost_yield_bp_one_way": cfg.cost_yield_bp,
        "research_start": str(eligible.index[0].date()),
        "research_end": str(eligible.index[-1].date()),
        "holdout_start": str(holdout.index[0].date()),
        "holdout_warning": "Chronological reporting only; NOT genuinely out-of-sample if design was informed by this period.",
        **_metrics(eligible),
        **_metrics(holdout, "holdout_"),
    }
    return BacktestResult(daily=daily, summary=summary)
