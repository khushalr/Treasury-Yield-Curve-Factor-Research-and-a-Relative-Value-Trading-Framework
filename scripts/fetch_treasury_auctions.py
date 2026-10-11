"""Download Treasury note CUSIP auction reference metadata (NOT trade quotes)."""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from src.research.cash_treasury import parse_auction_records

ENDPOINT = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
FIELDS = "cusip,security_type,security_term,auction_date,issue_date,maturity_date,int_rate"


def download_auction_catalog(as_of: date, page_size: int = 500) -> dict:
    if not 1 <= page_size <= 1000:
        raise ValueError("Invalid page size.")
    records = []
    start = as_of - timedelta(days=365*12)
    for page in range(1, 21):
        params = {
            "fields": FIELDS,
            "filter": f"security_type:eq:Note,auction_date:gte:{start.isoformat()},auction_date:lte:{as_of.isoformat()}",
            "sort": "-auction_date", "page[size]": page_size, "page[number]": page,
        }
        req = Request(ENDPOINT+"?"+urlencode(params),
                      headers={"User-Agent": "TreasuryButterflyResearch/1.0", "Accept": "application/json"})
        with urlopen(req, timeout=40) as response:
            data = response.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("Treasury response exceeded 4MB page safety limit.")
        parsed = json.loads(data)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), list):
            raise ValueError("Unexpected Treasury response.")
        records.extend(parsed["data"])
        if len(parsed["data"]) < page_size:
            break
    else:
        raise ValueError("Treasury auction pagination exceeded safety limit.")
    if not parse_auction_records(records, as_of):
        raise ValueError("No valid note records in response.")
    return {
        "source": ENDPOINT, "as_of": as_of.isoformat(),
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "records": records, "description": "Auction identifiers only; NOT executable prices.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", type=date.fromisoformat, required=True)
    p.add_argument("--output", type=Path, default=Path("data/treasury_note_auctions.json"))
    args = p.parse_args()
    payload = download_auction_catalog(args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_name(args.output.name+".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"Saved {len(payload['records'])} auction records to {args.output}")


if __name__ == "__main__":
    main()
