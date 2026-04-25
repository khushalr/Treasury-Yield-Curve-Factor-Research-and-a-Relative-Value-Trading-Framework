#!/usr/bin/env python3
"""Run daily signal pipeline in safe non-execution mode."""
from __future__ import annotations

import logging
from pathlib import Path

from src.config import PipelineConfig
from src.data.fed_curve_loader import load_fed_curve_data, validate_curve_data
from src.reporting.daily_report import write_daily_report
from src.research.fly_model import build_fly_series
from src.research.pca_model import compute_yield_changes, fit_rolling_pca
from src.research.signal_engine import generate_signals
from src.trading.instrument_mapper import map_instruments
from src.trading.order_builder import build_order_tickets
from src.trading.position_sizer import size_target_positions
from src.trading.risk_checks import run_risk_checks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
LOGGER = logging.getLogger("run_daily_signal")


def main() -> None:
    cfg = PipelineConfig()
    curve = load_fed_curve_data(cfg.data_path, cfg.selected_tenors)
    validation = validate_curve_data(curve, cfg.selected_tenors, cfg.stale_data_max_days)

    clean_curve = curve.dropna(subset=cfg.selected_tenors)
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
        mapped = map_instruments(sized.target_exposures, cfg.mode, cfg.etf_proxy_map)
        target_pos = {m.instrument: m.target_exposure for m in mapped}
        orders = build_order_tickets(
            target_pos,
            {},
            str(latest_date.date()),
            cfg.min_trade_size,
            cfg.max_position_change,
            dry_run=True,
        )
    else:
        mapped = []
        orders = []
        LOGGER.warning("Pre-risk checks failed; skipping order-ticket generation.")

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
        Path(cfg.reports_dir),
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
