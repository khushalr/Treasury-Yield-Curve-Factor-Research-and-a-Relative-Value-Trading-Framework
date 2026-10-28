"""Convert model signal into target abstract DV01 positions."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class SizingResult:
    """Sized target positions and diagnostics."""

    target_exposures: dict[int, float]
    gross_dv01: float
    notes: list[str]


def size_target_positions(
    signal_strength: float,
    fly_weights: dict[int, float],
    residual_vol: float,
    target_daily_vol: float,
    max_gross_dv01: float,
    max_leg_dv01: float,
) -> SizingResult:
    """Apply simple volatility targeting + caps to derive target tenor DV01 exposures."""

    notes: list[str] = []
    if max_gross_dv01 <= 0 or max_leg_dv01 <= 0 or target_daily_vol <= 0:
        raise ValueError("Risk caps and target_daily_vol must be strictly positive.")
    base = np.array([fly_weights[k] for k in sorted(fly_weights)], dtype=float)
    if not np.isfinite(base).all() or not np.isfinite(signal_strength):
        notes.append("Invalid signal or hedge weights; flat exposure.")
        return SizingResult({k: 0.0 for k in fly_weights}, 0.0, notes)
    if not np.isfinite(residual_vol) or residual_vol <= 0:
        notes.append("Residual volatility unavailable; flat exposure.")
        return SizingResult({k: 0.0 for k in fly_weights}, 0.0, notes)
    denom = float(np.sum(np.abs(base)))
    if denom == 0 or signal_strength == 0:
        return SizingResult({k: 0.0 for k in fly_weights}, 0.0, notes)

    scale = target_daily_vol / residual_vol
    gross_target = min(max_gross_dv01, abs(signal_strength) * max_gross_dv01 * scale)
    # DV01 is bond PRICE sensitivity. It has the opposite sign of the
    # yield-fly exposure ("short_fly" when the yield residual is high).
    raw = -np.sign(signal_strength) * gross_target * base / denom
    # Scale the entire hedge uniformly; independent leg clipping breaks PC neutrality.
    peak = float(np.max(np.abs(raw)))
    if peak > max_leg_dv01:
        raw *= max_leg_dv01 / peak
        notes.append("Whole hedge scaled to respect the per-leg DV01 cap.")
    exposures = {k: float(v) for k, v in zip(sorted(fly_weights), raw)}
    return SizingResult(exposures, float(np.sum(np.abs(raw))), notes)
