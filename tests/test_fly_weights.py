from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.fly_model import build_fly_series
from src.research.pca_model import compute_yield_changes, fit_rolling_pca


def test_pca_does_not_use_future_data() -> None:
    idx = pd.date_range("2020-01-01", periods=40, freq="B")
    curve = pd.DataFrame(
        {
            5: np.linspace(2.0, 3.0, 40),
            7: np.linspace(2.1, 3.1, 40),
            10: np.linspace(2.2, 3.2, 40),
        },
        index=idx,
    )
    yc = compute_yield_changes(curve)
    result = fit_rolling_pca(yc, window=20)

    check_date = list(result.loadings.keys())[0]
    assert check_date == yc.index[19]


def test_fly_uses_prior_day_loadings_for_current_residual() -> None:
    idx = pd.date_range("2020-01-01", periods=80, freq="B")
    rng = np.random.default_rng(4)
    curve = pd.DataFrame(
        {
            5: 3 + np.cumsum(rng.normal(0, 0.01, len(idx))),
            7: 3.2 + np.cumsum(rng.normal(0, 0.01, len(idx))),
            10: 3.4 + np.cumsum(rng.normal(0, 0.01, len(idx))),
        },
        index=idx,
    )
    yc = compute_yield_changes(curve)
    pca = fit_rolling_pca(yc, window=30)
    fly = build_fly_series(yc, pca.loadings, [5, 7, 10])

    dt = fly.weights.index[-1]
    loading_dt = fly.loading_date_used.loc[dt]
    assert loading_dt < dt


def test_fly_weights_are_pc1_pc2_neutral() -> None:
    idx = pd.date_range("2020-01-01", periods=80, freq="B")
    rng = np.random.default_rng(5)
    curve = pd.DataFrame(
        {
            5: 3 + np.cumsum(rng.normal(0, 0.01, len(idx))),
            7: 3.2 + np.cumsum(rng.normal(0, 0.01, len(idx))),
            10: 3.4 + np.cumsum(rng.normal(0, 0.01, len(idx))),
        },
        index=idx,
    )
    yc = compute_yield_changes(curve)
    pca = fit_rolling_pca(yc, window=30)
    fly = build_fly_series(yc, pca.loadings, [5, 7, 10])

    dt = fly.weights.index[-1]
    loading_dt = fly.loading_date_used.loc[dt]
    w = fly.weights.loc[dt].values
    l = pca.loadings[loading_dt].loc[[5, 7, 10], ["PC1", "PC2"]].values
    exposure = w @ l
    assert abs(exposure[0]) < 1e-6
    assert abs(exposure[1]) < 1e-6
