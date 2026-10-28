"""Signal generation for the PCA-neutral fly residual."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class SignalFrame:
    """Container around signal dataframe."""

    frame: pd.DataFrame


def generate_signals(
    fly_residual: pd.Series,
    fly_weights: pd.DataFrame,
    entry_z: float,
    signal_cap: float,
    rolling_window: int,
) -> SignalFrame:
    """Generate mean-reversion signals from fly residual z-scores.

    The z-score uses only information known before the signal date by computing
    rolling moments on ``fly_residual.shift(1)`` to avoid same-day leakage.
    """

    hist_residual = fly_residual.shift(1)
    mean = hist_residual.rolling(rolling_window, min_periods=rolling_window).mean()
    std = hist_residual.rolling(rolling_window, min_periods=rolling_window).std(ddof=0)
    z = (fly_residual - mean) / std.replace(0.0, np.nan)

    if entry_z <= 0 or signal_cap <= 0 or rolling_window < 2:
        raise ValueError("Positive entry_z/signal_cap and rolling_window >= 2 required.")
    raw_signal = -z
    active = np.isfinite(z) & (np.abs(z) >= entry_z)
    clipped_signal = raw_signal.clip(lower=-signal_cap, upper=signal_cap).where(active, 0.0)

    direction = np.where(active & (z > 0), "short_fly", np.where(active & (z < 0), "long_fly", "flat"))
    no_trade_reason = np.where(~np.isfinite(z), "insufficient/invalid history",
                               np.where(~active, "|z| below entry threshold", ""))

    out = pd.DataFrame(
        {
            "date": fly_residual.index,
            "z_score": z.values,
            "raw_signal": raw_signal.values,
            "clipped_signal": clipped_signal.values,
            "trade_direction": direction,
            "no_trade_reason": no_trade_reason,
        }
    ).set_index("date")

    out = out.join(fly_weights.add_prefix("w_"), how="left")
    # This is a dimensionless signal, not an instrument DV01 or order quantity.
    out["target_signal"] = out["clipped_signal"]

    return SignalFrame(frame=out)
