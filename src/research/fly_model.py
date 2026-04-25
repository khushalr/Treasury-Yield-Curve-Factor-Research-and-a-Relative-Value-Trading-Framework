"""Butterfly construction and residual computation."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FlyResult:
    """Output for fly weights and residual values."""

    weights: pd.DataFrame
    residual: pd.Series
    loading_date_used: pd.Series


def _solve_pc_neutral_weights(loadings: pd.DataFrame, tenors: list[int]) -> np.ndarray:
    tenor_loadings = loadings.loc[tenors, ["PC1", "PC2"]].values
    # Enforce middle leg (+1 on 7Y by default) and solve w1,w3 to neutralize PC1/PC2.
    # A * x = b where x=[w5,w10], w7 fixed at 1.
    a = tenor_loadings[[0, 2], :].T
    b = -tenor_loadings[1, :]
    x, *_ = np.linalg.lstsq(a, b, rcond=None)
    w = np.array([x[0], 1.0, x[1]], dtype=float)
    return w


def _latest_loading_before(
    dt: pd.Timestamp,
    loading_dates: list[pd.Timestamp],
) -> pd.Timestamp | None:
    prior = [d for d in loading_dates if d < dt]
    return prior[-1] if prior else None


def build_fly_series(
    yield_changes: pd.DataFrame,
    rolling_loadings: dict[pd.Timestamp, pd.DataFrame],
    tenors: list[int],
) -> FlyResult:
    """Build rolling 5Y-7Y-10Y fly that is approximately PC1/PC2 neutral.

    For a residual observed at date ``t``, weights are computed from loadings fit on
    information available strictly before ``t``.
    """

    rows: list[dict[str, float | pd.Timestamp]] = []
    residual_vals: list[dict[str, float | pd.Timestamp]] = []
    loading_used_rows: list[dict[str, pd.Timestamp]] = []

    loading_dates = sorted(rolling_loadings.keys())

    for dt in yield_changes.index:
        loading_dt = _latest_loading_before(dt, loading_dates)
        if loading_dt is None:
            continue

        load_df = rolling_loadings[loading_dt]
        if not np.isfinite(load_df[["PC1", "PC2"]].values).all():
            LOGGER.warning("Non-finite PC1/PC2 loadings at %s; skipping fly weight calc.", loading_dt)
            continue

        w = _solve_pc_neutral_weights(load_df, tenors)
        if np.any(np.abs(w) > 20):
            LOGGER.warning("Unstable fly weights at %s: %s", loading_dt, w)

        if "PC3" in load_df.columns and abs(load_df.loc[tenors[1], "PC3"]) < 1e-6:
            LOGGER.warning("PC3 belly loading near zero at %s; curvature interpretation may be weak.", loading_dt)

        yc = yield_changes.loc[dt, tenors].values
        fly_value = float(np.dot(w, yc))

        rows.append({"date": dt, str(tenors[0]): w[0], str(tenors[1]): w[1], str(tenors[2]): w[2]})
        residual_vals.append({"date": dt, "fly_residual": fly_value})
        loading_used_rows.append({"date": dt, "loading_date": loading_dt})

    wdf = pd.DataFrame(rows).set_index("date")
    rdf = pd.DataFrame(residual_vals).set_index("date")["fly_residual"]
    ldf = pd.DataFrame(loading_used_rows).set_index("date")["loading_date"]
    return FlyResult(weights=wdf, residual=rdf, loading_date_used=ldf)
