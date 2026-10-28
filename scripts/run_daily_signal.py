#!/usr/bin/env python3
"""Run daily signal pipeline in safe non-execution mode."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.config import PipelineConfig
from src.data.fed_curve_loader import load_fed_curve_data, validate_curve_data
from src.reporting.daily_report import write_daily_report
from src.research.fly_model import build_fly_series
from src.research.pca_model import compute_yield_changes, fit_rolling_pca
from src.research.signal_engine import generate_signals
from src.trading.position_sizer import size_target_positions
from src.trading.risk_checks import run_risk_checks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
LOGGER = logging.getLogger("run_daily_signal")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily research signal (no broker orders).")
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--as-of", type=str, default=None, help="Historical as-of YYYY-MM-DD")
    parser.add_argument("--pca-window", type=int, default=None)
    parser.add_argument("--signal-window", type=int, default=None)
    args = parser.parse_args()

    cfg = PipelineConfig()
    if args.pca_window is not None:
        cfg.rolling_pca_window = args.pca_window
    if args.signal_window is not None:
        cfg.rolling_signal_window = args.signal_window
    as_of = pd.Timestamp(args.as_of).normalize() if args.as_of else pd.Timestamp.utcnow().tz_localize(None).normalize()
    data_path = args.data or cfg.data_path
    curve = load_fed_curve_data(data_path, cfg.pca_tenors)
    curve = curve.loc[curve.index <= as_of]
    validation = validate_curve_data(curve, cfg.pca_tenors, cfg.stale_data_max_days, reference_date=as_of)
    if validation.errors:
        LOGGER.warning("Research signal will be generated, but risk gates will fail: %s", validation.errors)

    clean_curve = curve.dropna(subset=cfg.pca_tenors)
    if clean_curve.empty:
        raise RuntimeError("No usable curve rows after dropping missing tenors.")

    yc = compute_yield_changes(clean_curve)
    pca = fit_rolling_pca(yc, cfg.rolling_pca_window)
    fly = build_fly_series(yc, pca.loadings, cfg.selected_tenors)
    signals = generate_signals(fly.residual, fly.weights, cfg.entry_z, cfg.signal_cap, cfg.rolling_signal_window).frame

    signal_slice = signals.dropna(subset=["z_score"])
    if signal_slice.empty:
        raise RuntimeError("No valid z-score available; check rolling windows and data sufficiency.")

    latest = signal_slice.iloc[-1]
    latest_date = signal_slice.index[-1]
    fly_weights = {t: float(latest[f"w_{t}"]) for t in cfg.selected_tenors}

    # Vol target uses historical residual volatility only (shifted by one day).
    residual_vol = float(fly.residual.shift(1).rolling(63, min_periods=20).std(ddof=0).iloc[-1])
    sized = size_target_positions(
        float(latest["clipped_signal"]),
        fly_weights,
        residual_vol,
        cfg.target_daily_vol,
        cfg.max_gross_dv01,
        cfg.max_leg_dv01,
    )

    # Pass 1 checks (before order construction).
    pre_risk = run_risk_checks(
        latest_curve_date=clean_curve.index[-1],
        signal_date=latest_date,
        missing_tenors=[] if validation.is_valid else cfg.selected_tenors,
        z_score=float(latest["z_score"]),
        entry_z=cfg.entry_z,
        gross_dv01=sized.gross_dv01,
        max_gross_dv01=cfg.max_gross_dv01,
        leg_exposures=sized.target_exposures,
        max_leg_dv01=cfg.max_leg_dv01,
        max_position_change=cfg.max_position_change,
        order_sizes=[],
        allow_trading=cfg.allow_trading,
        paper_trading=cfg.paper_trading,
        live_trading=cfg.live_trading,
        bid_ask_bps=None,
        max_bid_ask_bps=cfg.max_bid_ask_bps,
        daily_loss=0.0,
        max_daily_loss=cfg.max_daily_loss,
        data_fresh=validation.is_valid,
    )

    if pre_risk.passed:
        # No contract price, validated DV01-to-quantity conversion or order intent.
        orders = []
    else:
        orders = []
        LOGGER.warning("Risk gate did not pass; report will include no tickets.")

    # Pass 2 checks (includes order size limits).
    final_risk = run_risk_checks(
        latest_curve_date=clean_curve.index[-1],
        signal_date=latest_date,
        missing_tenors=[] if validation.is_valid else cfg.selected_tenors,
        z_score=float(latest["z_score"]),
        entry_z=cfg.entry_z,
        gross_dv01=sized.gross_dv01,
        max_gross_dv01=cfg.max_gross_dv01,
        leg_exposures=sized.target_exposures,
        max_leg_dv01=cfg.max_leg_dv01,
        max_position_change=cfg.max_position_change,
        order_sizes=[o.quantity for o in orders],
        allow_trading=cfg.allow_trading,
        paper_trading=cfg.paper_trading,
        live_trading=cfg.live_trading,
        bid_ask_bps=None,
        max_bid_ask_bps=cfg.max_bid_ask_bps,
        daily_loss=0.0,
        max_daily_loss=cfg.max_daily_loss,
        data_fresh=validation.is_valid and pre_risk.passed,
    )

    paths = write_daily_report(
        args.output or Path(cfg.reports_dir),
        latest_date,
        clean_curve.index[-1],
        latest,
        orders,
        final_risk,
        cfg.mode,
        cfg.dry_run,
    )
    LOGGER.info("Saved reports: %s", paths)


if __name__ == "__main__":
    main()
