from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.reporting.daily_report import write_daily_report


def test_daily_report_includes_mode_field(tmp_path: Path) -> None:
    signal_date = pd.Timestamp("2025-01-15")
    row = pd.Series({"z_score": 1.0, "trade_direction": "flat", "target_dv01": 0.0, "w_5": -0.5, "w_7": 1.0, "w_10": -0.5})
    paths = write_daily_report(
        out_dir=tmp_path,
        report_date=signal_date,
        latest_curve_date=signal_date,
        signal_row=row,
        proposed_orders=[],
        risk_result={"passed": False},
        mode="paper_synthetic",
        dry_run=True,
    )

    payload = json.loads(paths["json"].read_text())
    assert payload["mode"] == "paper_synthetic"
