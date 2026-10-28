#!/usr/bin/env python3
"""Generate an offline, deterministic, clearly synthetic Fed-format curve fixture."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/demo_curve.csv"))
    args = parser.parse_args()

    tenors = np.array([1, 2, 3, 5, 7, 10, 20, 30])
    dates = pd.bdate_range("2025-01-02", periods=260)
    rng = np.random.default_rng(2026)
    level = np.cumsum(rng.normal(0, 0.015, len(dates)))
    slope = np.cumsum(rng.normal(0, 0.005, len(dates)))
    curve = np.cumsum(rng.normal(0, 0.003, len(dates)))
    shape = (tenors - 7.0) / 23.0
    hump = np.exp(-((tenors - 7.0) / 7.0) ** 2)
    yields = (3.5 + 0.03 * tenors + level[:, None] +
              slope[:, None] * shape + curve[:, None] * hump +
              rng.normal(0, 0.002, (len(dates), len(tenors))))
    frame = pd.DataFrame(yields, columns=[f"SVENY{t:02d}" for t in tenors])
    frame.insert(0, "Date", dates.strftime("%Y-%m-%d"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        out.write("Synthetic fixture for tests and demos; NOT Federal Reserve data\n")
        frame.to_csv(out, index=False)
    print(f"Generated {len(frame)} synthetic dates: {args.output}")


if __name__ == "__main__":
    main()
