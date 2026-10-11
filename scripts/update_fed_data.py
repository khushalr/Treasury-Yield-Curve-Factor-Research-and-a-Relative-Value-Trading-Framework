#!/usr/bin/env python3
"""Safely refresh the Federal Reserve's weekly nominal fitted Treasury curve CSV.

Source: https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv
Downloads the complete official file; does not concatenate overlapping records.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
REQUIRED = {"Date", "SVENY05", "SVENY07", "SVENY10"}
MAX_BYTES = 40_000_000


def inspect_csv(payload: bytes) -> tuple[str, int]:
    """Return latest observation date (ISO) and count after structural checks."""
    text = payload.decode("utf-8-sig")
    lines = text.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("Date,")), None)
    if header_idx is None:
        raise ValueError("Missing expected Fed CSV header.")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    fields = set(reader.fieldnames or [])
    if not REQUIRED.issubset(fields):
        raise ValueError(f"Missing columns: {sorted(REQUIRED - fields)}")
    from datetime import datetime
    latest = None
    count = 0
    seen = set()
    for row in reader:
        raw = (row.get("Date") or "").strip()
        if not raw:
            continue
        try:
            # Official Fed CSV dates are ISO YYYY-MM-DD, not day-first.
            dt = datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
        except ValueError as exc:
            raise ValueError(f"Unexpected observation date: {raw!r}") from exc
        if dt in seen:
            raise ValueError(f"Duplicate observation date: {dt}")
        if latest is not None and dt <= latest:
            raise ValueError("Observations not strictly increasing.")
        seen.add(dt)
        latest = dt
        count += 1
    if count < 1000 or latest is None:
        raise ValueError(f"Unusually short Fed dataset: {count} rows")
    return latest, count


def update(path: Path, source: str = SOURCE, allow_shrink: bool = False) -> bool:
    headers = {"User-Agent": "TreasuryResearchDataUpdater/1.0 (research)"}
    request = Request(source, headers=headers)
    with urlopen(request, timeout=50) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Unexpectedly large source file.")
    new_date, new_count = inspect_csv(payload)
    if path.exists():
        previous = path.read_bytes()
        old_date, old_count = inspect_csv(previous)
        if new_date < old_date:
            raise ValueError(f"Remote dataset regressed from {old_date} to {new_date}.")
        if new_count < old_count and not allow_shrink:
            raise ValueError(f"Remote dataset shrunk ({old_count} -> {new_count}); refusing overwrite.")
        if previous == payload:
            print(f"Already up to date: {new_date} ({new_count} rows)")
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_bytes(payload)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    print(f"Updated {path}: through {new_date}; {new_count} rows")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=Path("feds200628.csv"))
    parser.add_argument("--allow-shrink", action="store_true", help="Manual-only recovery for an intentional source revision")
    args = parser.parse_args()
    update(args.path, allow_shrink=args.allow_shrink)


if __name__ == "__main__":
    main()
