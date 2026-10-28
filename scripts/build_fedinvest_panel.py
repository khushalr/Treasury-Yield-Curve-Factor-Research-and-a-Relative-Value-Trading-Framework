"""Produce CUSIP-level, same-date valuation comparisons; never interpret as P&L."""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
import pandas as pd

from src.data.fed_curve_loader import load_fed_curve_data
from src.data.fip_prices import FedInvestReferencePrice, prepare_reference_panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, default=Path("data/fedinvest_reference_prices.csv"))
    parser.add_argument("--auctions", type=Path, default=Path("data/treasury_note_auctions.json"))
    parser.add_argument("--curve", type=Path, default=Path("feds200628.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports/fedinvest_reference"))
    args = parser.parse_args()
    raw = pd.read_csv(args.references, dtype={"cusip": str})
    required = {"date", "cusip", "security_type", "reference_buy_per_100",
                "reference_sell_per_100", "source_url"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Missing price panel columns: {sorted(required-set(raw.columns))}")
    refs = []
    for r in raw.to_dict(orient="records"):
        eod = r.get("reference_eod_per_100")
        refs.append(FedInvestReferencePrice(
            date=date.fromisoformat(str(r["date"])), cusip=str(r["cusip"]).strip(),
            security_type=str(r["security_type"]),
            reference_buy_per_100=float(r["reference_buy_per_100"]),
            reference_sell_per_100=float(r["reference_sell_per_100"]),
            reference_eod_per_100=float(eod) if pd.notna(eod) else None,
            source_url=str(r["source_url"])))
    catalog = json.loads(args.auctions.read_text(encoding="utf-8"))
    if not isinstance(catalog.get("records"), list):
        raise ValueError("Auction metadata missing records.")
    dates = sorted({r.date for r in refs})
    if not dates:
        raise ValueError("No reference prices supplied.")
    if date.fromisoformat(catalog["as_of"]) < dates[-1]:
        raise ValueError("Auction catalog predates reference panel.")
    curve = load_fed_curve_data(args.curve, list(range(1, 31)))
    panel, omissions = prepare_reference_panel(refs, catalog["records"], curve)
    args.out.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out/"matched_valuation_panel.csv", index=False)
    omissions.to_csv(args.out/"excluded_dates.csv", index=False)
    summary = {
        "price_source": "FedInvest government-account NON-EXECUTABLE reference",
        "days_with_references": len(dates),
        "complete_matched_days": panel["date"].nunique() if not panel.empty else 0,
        "excluded_days": len(omissions),
        "matched_bond_observations": len(panel),
        "portfolio_pnl_or_sharpe_available": False,
        "note": "Theoretical fitted-curve vs government-account prices; not executable trades."
    }
    (args.out/"quality_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__=="__main__":
    main()
