"""Create a non-executable cash Treasury research valuation report."""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
import pandas as pd
from src.data.fed_curve_loader import load_fed_curve_data
from src.research.cash_treasury import (
    construct_paper_fly, parse_auction_records, read_quotes, select_cash_notes, value_notes,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", type=date.fromisoformat, required=True)
    p.add_argument("--auction-file", type=Path, default=Path("data/treasury_note_auctions.json"))
    p.add_argument("--quotes-file", type=Path, required=True)
    p.add_argument("--fed-file", type=Path, default=Path("feds200628.csv"))
    p.add_argument("--direction", type=int, choices=(-1, 0, 1), required=True)
    p.add_argument("--gross-dv01", type=float, default=100.0)
    p.add_argument("--max-cusip-gap", type=float, default=.85)
    p.add_argument("--output", type=Path, default=Path("reports/cash_paper_valuation.json"))
    args = p.parse_args()
    catalog = json.loads(args.auction_file.read_text(encoding="utf-8"))
    if catalog.get("as_of") != args.as_of.isoformat() or not isinstance(catalog.get("records"), list):
        raise ValueError("Auction catalog must contain records for exactly --as-of.")
    selected = select_cash_notes(
        parse_auction_records(catalog["records"], args.as_of),
        args.as_of, maximum_maturity_gap_years=args.max_cusip_gap)
    quotes = read_quotes(args.quotes_file, args.as_of)
    curve = load_fed_curve_data(args.fed_file, list(range(1, 31)))
    date_index = pd.Timestamp(args.as_of)
    if date_index not in curve.index:
        raise ValueError("No matching-date Fed fitted curve; refuse to mix observation dates.")
    row = curve.loc[date_index]
    if row.isna().any():
        raise ValueError("Fitted curve has missing tenor data.")
    fitted = {t: float(row[t]) for t in range(1, 31)}
    values = value_notes(selected, quotes, args.as_of, fitted)
    report = construct_paper_fly(values, args.direction, args.gross_dv01)
    report.update({
        "as_of": args.as_of.isoformat(),
        "auction_source": catalog.get("source"),
        "auction_retrieved_utc": catalog.get("retrieved_utc"),
        "fed_curve_file": str(args.fed_file), "quotes_file": str(args.quotes_file),
        "warning": "Research only; no broker connection or order submission.",
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
