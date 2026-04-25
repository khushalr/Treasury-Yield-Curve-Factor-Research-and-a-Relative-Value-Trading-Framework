from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.signal_engine import generate_signals
from src.trading.order_builder import build_order_tickets


def test_zscore_signal_direction_and_threshold() -> None:
    idx = pd.date_range("2024-01-01", periods=9, freq="B")
    residual = pd.Series([0, 1, -1, 1, -1, 1, -1, 0, 10], index=idx, dtype=float)
    weights = pd.DataFrame({"5": [0.5] * 9, "7": [1.0] * 9, "10": [0.5] * 9}, index=idx)

    frame = generate_signals(residual, weights, entry_z=1.5, signal_cap=3.0, rolling_window=5).frame
    last = frame.iloc[-1]
    assert last["trade_direction"] == "short_fly"
    assert last["raw_signal"] < 0


def test_long_signal_when_negative_dislocation() -> None:
    idx = pd.date_range("2024-01-01", periods=9, freq="B")
    residual = pd.Series([0, 1, -1, 1, -1, 1, -1, 0, -10], index=idx, dtype=float)
    weights = pd.DataFrame({"5": [0.5] * 9, "7": [1.0] * 9, "10": [0.5] * 9}, index=idx)

    frame = generate_signals(residual, weights, entry_z=1.5, signal_cap=3.0, rolling_window=5).frame
    last = frame.iloc[-1]
    assert last["trade_direction"] == "long_fly"
    assert last["raw_signal"] > 0


def test_no_trade_below_entry_and_clipping() -> None:
    idx = pd.date_range("2024-01-01", periods=12, freq="B")
    residual = pd.Series(np.linspace(0, 1, 12), index=idx, dtype=float)
    weights = pd.DataFrame({"5": [0.5] * 12, "7": [1.0] * 12, "10": [0.5] * 12}, index=idx)

    frame = generate_signals(residual, weights, entry_z=2.5, signal_cap=0.5, rolling_window=5).frame
    assert (frame["clipped_signal"].abs().dropna() <= 0.5 + 1e-12).all()
    assert frame.iloc[-1]["trade_direction"] == "flat"


def test_zscore_uses_only_prior_history() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="B")
    residual = pd.Series([0, 1, -1, 1, -1, 1, -1, 10], index=idx, dtype=float)
    weights = pd.DataFrame({"5": [0.5] * 8, "7": [1.0] * 8, "10": [0.5] * 8}, index=idx)

    frame = generate_signals(residual, weights, entry_z=2.0, signal_cap=3.0, rolling_window=5).frame

    # Prior-history window has low variance, so current spike should produce large z-score.
    assert frame.iloc[-1]["z_score"] > 5


def test_order_builder_defaults_to_dry_run() -> None:
    tickets = build_order_tickets({"SYNTH_5Y": 10.0}, {"SYNTH_5Y": 0.0}, "2024-01-01")
    assert len(tickets) == 1
    assert tickets[0].dry_run is True
