"""Download an auditable CUSIP-level FedInvest *reference* price history.

Not executable broker quotes. Never feed this file to read_quotes().
"""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.data.fip_prices import parse_fedinvest_rows

ENDPOINT = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/fip_rates_prices"
FIELDS = "data_date,cusip,security_type,buy_amt,sell_amt,end_of_day_amt"


def download(start: date, end: date, page_size: int = 1000) -> list:
    if start > end or not 1 <= page_size <= 1000:
        raise ValueError("Invalid date interval or page size.")
    output = []
    page = 1
    while page <= 1000:
        params = {
            "fields": FIELDS,
            "filter": f"data_date:gte:{start},data_date:lte:{end}",
            "sort": "data_date,cusip", "page[number]": page, "page[size]": page_size,
        }
        url = ENDPOINT+"?"+urlencode(params)
        req = Request(url, headers={"User-Agent": "TreasuryButterflyResearch/1.0",
                                    "Accept":"application/json"})
        with urlopen(req, timeout=45) as response:
            data = response.read(8_000_001)
        if len(data) > 8_000_000:
            raise ValueError("API page exceeds size limit.")
        body = json.loads(data)
        if not isinstance(body.get("data"), list):
            raise ValueError("Unexpected Fiscal Data response.")
        output.extend(body["data"])
        page_rows = len(body["data"])
        print(f"Downloaded page {page} ({page_rows} rows)")
        if page_rows < page_size:
            break
        page += 1
    else:
        raise RuntimeError("Pagination cap reached; shorten date range.")
    parsed = parse_fedinvest_rows(output, ENDPOINT, start, end)
    if not parsed:
        raise ValueError("No usable 2-sided Note references in requested period.")
    return parsed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--output", type=Path, default=Path("data/fedinvest_reference_prices.csv"))
    args = p.parse_args()
    prices = download(args.start, args.end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "date","cusip","security_type","reference_buy_per_100",
            "reference_sell_per_100","reference_eod_per_100","source_url"])
        writer.writeheader()
        for price in prices:
            writer.writerow({
                "date":price.date.isoformat(),"cusip":price.cusip,
                "security_type":price.security_type,
                "reference_buy_per_100":price.reference_buy_per_100,
                "reference_sell_per_100":price.reference_sell_per_100,
                "reference_eod_per_100":price.reference_eod_per_100,
                "source_url":price.source_url,
            })
    print(f"Saved {len(prices)} Treasury NOTE government-account reference quotes to {args.output}")
    print("Do not interpret these as executable dealer bid/ask prices.")


if __name__ == "__main__":
    main()
