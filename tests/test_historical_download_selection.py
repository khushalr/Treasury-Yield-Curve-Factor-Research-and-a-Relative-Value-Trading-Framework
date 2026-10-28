"""Offline checks for preselecting CUSIPs instead of full-universe downloads."""
from datetime import date
import json
import pytest
from scripts.fetch_fedinvest_prices import selected_cusips, download


def test_fedinvest_download_rejects_unbounded_unselected_requests():
    with pytest.raises(ValueError, match="CUSIP"):
        download(date(2025, 1, 1), date(2025, 1, 2), [])


def test_historical_selection_rejects_incomplete_catalog(tmp_path):
    p = tmp_path / "auction.json"
    p.write_text(json.dumps({"as_of": "2025-03-31", "records": []}))
    with pytest.raises(ValueError, match="No selectable"):
        selected_cusips(p, date(2025, 1, 1), date(2025, 1, 3))


def test_historical_selection_rejects_catalog_prior_to_end(tmp_path):
    p = tmp_path / "auction.json"
    p.write_text(json.dumps({"as_of": "2025-01-01", "records": []}))
    with pytest.raises(ValueError, match="predates"):
        selected_cusips(p, date(2025, 1, 1), date(2025, 1, 3))
