#!/usr/bin/env python3
"""Run the non-executable synthetic Treasury curve research backtest."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.data.fed_curve_loader import load_fed_curve_data
from src.research.backtest import BacktestConfig, run_synthetic_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('feds200628.csv'))
    parser.add_argument('--output', type=Path, default=Path('reports/backtest'))
    parser.add_argument('--pca-window', type=int, default=504)
    parser.add_argument('--z-window', type=int, default=126)
    parser.add_argument('--entry-z', type=float, default=2.5)
    parser.add_argument('--exit-z', type=float, default=0.5)
    parser.add_argument('--cost-yield-bp', type=float, default=.25)
    args = parser.parse_args()
    cfg = BacktestConfig(
        pca_window=args.pca_window, z_window=args.z_window,
        entry_z=args.entry_z, exit_z=args.exit_z,
        cost_yield_bp=args.cost_yield_bp,
    )
    curve = load_fed_curve_data(args.data, list(cfg.tenors))
    original = len(curve)
    curve = curve.dropna(subset=list(cfg.tenors))
    result = run_synthetic_backtest(curve, cfg)
    args.output.mkdir(parents=True, exist_ok=True)
    csv = args.output / 'synthetic_backtest_daily.csv'
    js = args.output / 'synthetic_backtest_summary.json'
    result.daily.to_csv(csv, index_label='date')
    payload = {
        'source_file': str(args.data),
        'source_rows': original,
        'rows_after_removing_incomplete_tenors': int(len(curve)),
        'parameter_config': asdict(cfg),
        **result.summary,
        'warning': (
            'NOT a tradable strategy backtest or percentage investment return. '
            'No as-of data vintages, pricing, carry, financing, convexity, or '
            'execution quotes. Source Fed nominal curve is revised/smoothed.'
        ),
    }
    js.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    print(f'Wrote {csv} and {js}')


if __name__ == '__main__':
    main()
