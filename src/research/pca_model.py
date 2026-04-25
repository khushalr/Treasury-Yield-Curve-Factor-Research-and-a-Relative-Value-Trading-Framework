"""Rolling PCA model for yield-curve factor extraction."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


@dataclass(slots=True)
class RollingPCAResult:
    """Container for rolling PCA outputs."""

    yield_changes: pd.DataFrame
    loadings: dict[pd.Timestamp, pd.DataFrame]
    explained_variance: pd.DataFrame
    factor_scores: pd.DataFrame


def compute_yield_changes(curve_df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily changes in yields.

    We use changes (first differences) rather than levels because yield levels are
    persistent/trending; PCA on levels overweights non-stationary level effects and
    can produce unstable, regime-sensitive components.
    """

    return curve_df.diff().dropna(how="any")


def fit_rolling_pca(yield_changes: pd.DataFrame, window: int, n_components: int = 3) -> RollingPCAResult:
    """Fit rolling PCA using only observations up to each date (no look-ahead)."""

    if len(yield_changes) < window:
        raise ValueError("Insufficient history for rolling PCA window.")

    loadings: dict[pd.Timestamp, pd.DataFrame] = {}
    var_rows: list[dict[str, float | pd.Timestamp]] = []
    score_rows: list[dict[str, float | pd.Timestamp]] = []

    for end_idx in range(window, len(yield_changes) + 1):
        hist = yield_changes.iloc[end_idx - window : end_idx]
        date_t = hist.index[-1]

        model = PCA(n_components=n_components)
        model.fit(hist.values)

        comp_names = [f"PC{i + 1}" for i in range(n_components)]
        loadings[date_t] = pd.DataFrame(model.components_.T, index=yield_changes.columns, columns=comp_names)

        var_row: dict[str, float | pd.Timestamp] = {"date": date_t}
        for i, ratio in enumerate(model.explained_variance_ratio_):
            var_row[f"PC{i + 1}"] = float(ratio)
        var_rows.append(var_row)

        latest_change = yield_changes.iloc[end_idx - 1].values.reshape(1, -1)
        score = model.transform(latest_change)[0]
        score_row: dict[str, float | pd.Timestamp] = {"date": date_t}
        for i, val in enumerate(score):
            score_row[f"PC{i + 1}"] = float(val)
        score_rows.append(score_row)

    explained = pd.DataFrame(var_rows).set_index("date")
    scores = pd.DataFrame(score_rows).set_index("date")

    return RollingPCAResult(yield_changes=yield_changes, loadings=loadings, explained_variance=explained, factor_scores=scores)
