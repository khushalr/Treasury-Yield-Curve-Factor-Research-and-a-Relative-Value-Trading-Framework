"""Download a bounded CUSIP-specific FedInvest reference-price history.

Requires historical auction metadata first. Values are government-account
reference prices, NOT executable dealer quotes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.data.fip_prices import parse_fedinvest_rows
from src.research.cash_treasury import parse_auction_records, select_cash_notes

ENDPOINT = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/fip_rates_prices"
FIELDS = "data_date,cusip,security_type,buy_amt,sell_amt,end_of_day_amt"


def selected_cusips(auction_file: Path, start: date, end: date) -> list[str]:
    """Return CUSIP union of three maturity-matched notes for each weekday."""
    catalog = json.loads(auction_file.read_text(encoding="utf-8"))
    records = catalog.get("records")
    if not isinstance(records, list) or date.fromisoformat(catalog["as_of"]) < end:
        raise ValueError("Auction catalog is missing or predates the requested end date.")
    selected: set[str] = set()
    day = start
    missed: list[str] = []
    while day <= end:
        if day.weekday() < 5:
            try:
                pool = parse_auction_records(records, day)
                selections = select_cash_notes(pool, day)
                selected.update(n.cusip for n in selections.values())
            except ValueError:
                missed.append(day.isoformat())
        day += timedelta(days=1)
    if not selected:
        raise ValueError("No selectable Treasury CUSIPs within requested historical period.")
    if missed:
        raise ValueError(
            f"Missing eligible historical auction references on {len(missed)} weekdays, "
            f"first {missed[0]}. Correct auction catalog before downloading."
        )
    return sorted(selected)


def download(start: date, end: date, cusips: list[str], page_size: int = 500) -> list:
    if start > end or not 1 <= page_size <= 1000 or not cusips:
        raise ValueError("Invalid date interval, page size or CUSIP selection.")
    unique = sorted(set(cusips))
    if any(len(v) != 9 or not v.isalnum() for v in unique):
        raise ValueError("Invalid Treasury CUSIP.")
    output = []
    # Small, disjoint CUSIP batches avoid downloading the full US security universe.
    for offset in range(0, len(unique), 15):
        batch = unique[offset:offset+15]
        page = 1
        while page <= 500:
            params = {
                "fields": FIELDS,
                "filter": (
                    f"data_date:gte:{start.isoformat()},data_date:lte:{end.isoformat()},"
                    f"cusip:in:({','.join(batch)})"
                ),
                "sort": "data_date,cusip",
                "page[number]": page, "page[size]": page_size,
            }
            req = Request(ENDPOINT+"?"+urlencode(params),
                          headers={"User-Agent": "TreasuryButterflyResearch/1.0",
                                   "Accept": "application/json"})
            with urlopen(req, timeout=45) as response:
                data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise ValueError("API page exceeds size limit.")
            body = json.loads(data)
            if not isinstance(body, dict) or not isinstance(body.get("data"), list):
                raise ValueError(f"Unexpected Fiscal Data response on page {page}.")
            rows = body["data"]
            output.extend(rows)
            print(f"Downloaded CUSIP batch {1+offset//15}, page {page} ({len(rows)} rows)")
            if len(rows) < page_size:
                break
            page += 1
        else:
            raise RuntimeError("Pagination cap reached; shorten date interval.")
    parsed = parse_fedinvest_rows(output, ENDPOINT, start, end)
    if not parsed:
        raise ValueError("No usable note reference prices; verify API schema, security_type and price units.")
    found = {p.cusip for p in parsed}
    if not found.intersection(unique):
        raise ValueError("No matched CUSIPs found.")
    return parsed


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--auction-file", type=Path, default=Path("data/treasury_note_auctions.json"))
    p.add_argument("--output", type=Path, default=Path("data/fedinvest_reference_prices.csv"))
    args = p.parse_args()
    chosen = selected_cusips(args.auction_file, args.start, args.end)
    print(f"Selected {len(chosen)} historical distinct CUSIPs, not the full market.")
    prices = download(args.start, args.end, chosen)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_name(args.output.name+".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "date", "cusip", "security_type", "reference_buy_per_100",
                "reference_sell_per_100", "reference_eod_per_100", "source_url"])
            writer.writeheader()
            for price in prices:
                writer.writerow({
                    "date": price.date.isoformat(), "cusip": price.cusip,
                    "security_type": price.security_type,
                    "reference_buy_per_100": price.reference_buy_per_100,
                    "reference_sell_per_100": price.reference_sell_per_100,
                    "reference_eod_per_100": price.reference_eod_per_100,
                    "source_url": price.source_url,
                })
        os.replace(tmp, args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"Saved {len(prices)} Treasury NOTE government-account reference quotes to {args.output}")
    print("These are not executable dealer bid/ask prices.")


if __name__ == "__main__":
    main()
