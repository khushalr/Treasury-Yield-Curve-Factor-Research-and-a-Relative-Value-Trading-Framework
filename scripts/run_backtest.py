#!/usr/bin/env python3
"""Reproduce an illustrative, cost-aware walk-forward Treasury fly study."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import PCA_TENORS
from src.data.fed_curve_loader import load_fed_curve_data
from src.research.backtest import run_walk_forward_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("feds200628.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/backtest"))
    parser.add_argument("--pca-window", type=int, default=126)
    parser.add_argument("--signal-window", type=int, default=63)
    parser.add_argument("--entry-z", type=float, default=2.5)
    parser.add_argument("--cost-bp", type=float, default=0.5)
    args = parser.parse_args()

    curve = load_fed_curve_data(args.data, PCA_TENORS).dropna()
    result = run_walk_forward_backtest(
        curve, pca_window=args.pca_window, signal_window=args.signal_window,
        entry_z=args.entry_z, cost_bp=args.cost_bp
    )
    args.output.mkdir(parents=True, exist_ok=True)
    csv_path = args.output / "daily_backtest.csv"
    json_path = args.output / "summary.json"
    result.daily.to_csv(csv_path, index_label="Date")
    json_path.write_text(json.dumps(result.summary, indent=2, allow_nan=False, default=str),
                         encoding="utf-8")
    print(json.dumps(result.summary, indent=2, default=str))
    print(f"Saved daily diagnostics to {csv_path} and {json_path}")


if __name__ == "__main__":
    main()
