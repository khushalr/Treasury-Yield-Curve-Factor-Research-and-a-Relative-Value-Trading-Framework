"""Smoke test the actual, bundled Fed dataset rather than only synthetic fixtures."""
from pathlib import Path

import pandas as pd

from src.data.fed_curve_loader import load_fed_curve_data

DATA = Path(__file__).resolve().parents[1] / "feds200628.csv"
PCA_TENORS = [1, 2, 3, 5, 7, 10, 20, 30]


def test_bundled_federal_reserve_curve_is_readable() -> None:
    assert DATA.is_file(), "Bundled Fed data are needed to reproduce research."
    frame = load_fed_curve_data(DATA, PCA_TENORS)
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert len(frame) > 1000
    complete = frame.dropna(subset=PCA_TENORS)
    assert len(complete) > 500
    assert complete.index.max() <= frame.index.max()
    assert all(pd.api.types.is_numeric_dtype(frame[t]) for t in PCA_TENORS)
