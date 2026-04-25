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
    if residual_vol <= 0 or np.isnan(residual_vol):
        scale = 0.0
        notes.append("Residual volatility unavailable; setting exposure to zero.")
    else:
        scale = target_daily_vol / residual_vol

    gross_target = min(max_gross_dv01, abs(signal_strength) * max_gross_dv01 * scale)
    base = np.array([fly_weights[k] for k in sorted(fly_weights)], dtype=float)
    denom = float(np.sum(np.abs(base))) if np.sum(np.abs(base)) > 0 else 1.0

    exposures: dict[int, float] = {}
    for tenor, w in sorted(fly_weights.items()):
        leg = float(np.sign(signal_strength) * gross_target * (w / denom))
        capped = float(np.clip(leg, -max_leg_dv01, max_leg_dv01))
        if capped != leg:
            notes.append(f"Leg cap applied at tenor {tenor}.")
        exposures[tenor] = capped

    gross = float(sum(abs(v) for v in exposures.values()))
    return SizingResult(target_exposures=exposures, gross_dv01=gross, notes=notes)
