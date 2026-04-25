"""Daily signal/report writer utilities."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd


def _serialize_obj(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def write_daily_report(
    out_dir: Path,
    report_date: pd.Timestamp,
    latest_curve_date: pd.Timestamp,
    signal_row: pd.Series,
    proposed_orders: list[Any],
    risk_result: Any,
    mode: str,
    dry_run: bool,
) -> dict[str, Path]:
    """Write markdown, JSON, and CSV daily reports."""

    out_dir.mkdir(parents=True, exist_ok=True)
    tag = report_date.strftime("%Y%m%d")

    payload = {
        "latest_curve_date": latest_curve_date.isoformat(),
        "signal_date": report_date.isoformat(),
        "z_score": float(signal_row.get("z_score", float("nan"))),
        "trade_direction": str(signal_row.get("trade_direction", "unknown")),
        "fly_weights": {k: float(v) for k, v in signal_row.items() if str(k).startswith("w_") and pd.notna(v)},
        "target_dv01": float(signal_row.get("target_dv01", 0.0)),
        "proposed_orders": [_serialize_obj(x) for x in proposed_orders],
        "risk_checks": _serialize_obj(risk_result),
        "mode": mode,
        "dry_run": dry_run,
        "explanation": "Trading is blocked unless all safety and risk checks pass.",
    }

    json_path = out_dir / f"daily_report_{tag}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_path = out_dir / f"daily_report_{tag}.csv"
    pd.DataFrame([payload]).drop(columns=["proposed_orders", "risk_checks", "fly_weights"]).to_csv(csv_path, index=False)

    md_path = out_dir / f"daily_report_{tag}.md"
    md_path.write_text(
        "\n".join(
            [
                f"# Daily Signal Report ({tag})",
                f"- Latest curve date: `{payload['latest_curve_date']}`",
                f"- Signal date: `{payload['signal_date']}`",
                f"- Latest z-score: `{payload['z_score']:.4f}`",
                f"- Trade direction: `{payload['trade_direction']}`",
                f"- Mode: `{payload['mode']}`",
                f"- Dry-run: `{payload['dry_run']}`",
                f"- Explanation: {payload['explanation']}",
                "",
                "## Proposed Orders",
                *[f"- `{o}`" for o in payload["proposed_orders"]],
                "",
                "## Risk Checks",
                f"- `{payload['risk_checks']}`",
            ]
        ),
        encoding="utf-8",
    )

    return {"json": json_path, "csv": csv_path, "md": md_path}
