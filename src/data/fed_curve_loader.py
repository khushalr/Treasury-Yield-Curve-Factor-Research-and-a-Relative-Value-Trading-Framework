"""Loader for Federal Reserve Treasury curve data used by the research notebook."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DataValidationResult:
    """Validation output for loaded curve data."""

    is_valid: bool
    warnings: list[str]
    errors: list[str]


def _find_header_line(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if line.startswith("Date,"):
                return idx
    raise ValueError("Could not find 'Date' header row in Fed curve CSV.")


def load_fed_curve_data(path: Path | str, tenors: list[int]) -> pd.DataFrame:
    """Load and clean Fed curve data for selected tenors.

    The source CSV includes metadata lines before the data header, so this function
    locates the `Date,...` header dynamically.
    """

    csv_path = Path(path)
    header_line = _find_header_line(csv_path)
    raw = pd.read_csv(csv_path, skiprows=header_line, na_values=["NA", ""])
    raw["Date"] = pd.to_datetime(raw["Date"], format="%Y-%m-%d", errors="raise")
    if raw["Date"].isna().any():
        raise ValueError("Missing Fed observation dates; refusing to drop rows silently.")
    if raw["Date"].duplicated().any():
        raise ValueError("Duplicate Fed observation dates.")
    raw = raw.set_index("Date").sort_index()

    cols = [f"SVENY{tenor:02d}" for tenor in tenors]
    missing = [c for c in cols if c not in raw.columns]
    if missing:
        raise ValueError(f"Missing expected tenor columns: {missing}")

    curve = raw[cols].apply(pd.to_numeric, errors="coerce")
    # The Federal Reserve has historically used -999.99 as missing-data sentinel.
    curve = curve.mask(curve <= -999.0)
    curve.columns = tenors
    return curve


def validate_curve_data(
    curve_df: pd.DataFrame,
    tenors: list[int],
    stale_data_max_days: int = 5,
) -> DataValidationResult:
    """Validate data quality checks used by trading risk guardrails."""

    warnings: list[str] = []
    errors: list[str] = []

    if curve_df.empty:
        errors.append("Curve dataset is empty.")
        return DataValidationResult(False, warnings, errors)

    missing_tenors = [t for t in tenors if t not in curve_df.columns]
    if missing_tenors:
        errors.append(f"Missing required tenors: {missing_tenors}")

    if not all(pd.api.types.is_numeric_dtype(curve_df[c]) for c in curve_df.columns):
        errors.append("Non-numeric values detected in curve columns.")

    if curve_df[tenors].isna().any().any():
        warnings.append("Missing yield observations detected; rows will be dropped downstream.")

    business_days = pd.date_range(curve_df.index.min(), curve_df.index.max(), freq="B")
    missing_dates = business_days.difference(curve_df.index)
    if len(missing_dates) > 0:
        warnings.append(f"Missing business dates detected: {len(missing_dates)}")

    latest_date = curve_df.index.max().date()
    now_utc = pd.Timestamp.utcnow().date()
    staleness = (now_utc - latest_date).days
    if staleness > stale_data_max_days:
        errors.append(
            f"Data is stale: latest point is {latest_date} ({staleness} days old)."
        )

    for msg in warnings:
        LOGGER.warning(msg)
    for msg in errors:
        LOGGER.error(msg)

    return DataValidationResult(len(errors) == 0, warnings, errors)
