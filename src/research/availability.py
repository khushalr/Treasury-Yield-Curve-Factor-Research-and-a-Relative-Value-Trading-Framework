"""Explicit timestamp alignment for independently supplied vintage observations.

This does not infer weekly release dates or certify the Fed latest-vintage CSV.
"""
import pandas as pd
import numpy as np


def asof_vintages(records, decisions):
    """Return latest observed date/version actually available at each decision.

    Required columns: observation_date, available_at, value. Dates are UTC-aware;
    available_at must be backed by source evidence, never an inferred row lag.
    """
    required = {"observation_date", "available_at", "value"}
    if not required.issubset(records.columns):
        raise ValueError("Missing vintage fields")
    data = records.copy()
    for c in ("observation_date", "available_at"):
        data[c] = pd.to_datetime(data[c], utc=True, errors="raise")
    if data[list(required)].isna().any().any():
        raise ValueError("Missing vintage values")
    if (data["available_at"] < data["observation_date"]).any():
        raise ValueError("Release precedes observation")
    if data.duplicated(["observation_date", "available_at"]).any():
        raise ValueError("Ambiguous duplicate vintage")
    if not np.isfinite(pd.to_numeric(data["value"], errors="raise")).all():
        raise ValueError("Nonfinite vintage value")
    times = pd.DatetimeIndex(pd.to_datetime(decisions, utc=True))
    if times.hasnans or not times.is_unique or not times.is_monotonic_increasing:
        raise ValueError("Decisions must be unique and increasing")
    data = data.sort_values(["observation_date", "available_at"])
    rows = []
    for timestamp in times:
        eligible = data.loc[data["available_at"] <= timestamp]
        if eligible.empty:
            rows.append({"decision_at": timestamp, "value": np.nan,
                         "observation_date": pd.NaT, "available_at": pd.NaT})
        else:
            row = eligible.iloc[-1]
            rows.append({"decision_at": timestamp, **row[list(required)].to_dict()})
    return pd.DataFrame(rows, columns=["decision_at", "value", "observation_date", "available_at"]).set_index("decision_at")
