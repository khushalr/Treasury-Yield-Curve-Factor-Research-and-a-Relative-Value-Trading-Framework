"""Fast offline regression checks for actual Fed ISO YYYY-MM-DD dates."""
import pytest
import pandas as pd

from scripts.update_fed_data import inspect_csv
from src.data.fed_curve_loader import load_fed_curve_data


def fixture_csv(rows):
    prefix = "Research data\nMetadata line\nDate,SVENY05,SVENY07,SVENY10\n"
    return (prefix + "\n".join(rows) + "\n").encode()


def test_day_first_dates_are_not_swapped(tmp_path):
    rows = [f"2026-02-{i:02d},4.1,4.2,4.3" for i in range(1, 13)]
    raw = fixture_csv(rows)
    # inspect_csv intentionally requires full historic file (>1000 obs)
    path = tmp_path / "sample.csv"
    path.write_bytes(raw)
    frame = load_fed_curve_data(path, [5, 7, 10])
    assert str(frame.index[0].date()) == "2026-02-01"
    assert str(frame.index[-1].date()) == "2026-02-12"
    assert len(frame) == 12


def test_uploader_rejects_non_chronological_dates():
    rows = [f"2026-02-{i:02d},4.1,4.2,4.3" for i in (2, 1)]
    with pytest.raises(ValueError, match="strictly increasing"):
        inspect_csv(fixture_csv(rows))


def test_uploader_rejects_wrong_columns():
    bad = b"Date,SVENY05,SVENY07\n2026-01-01,1,2\n"
    with pytest.raises(ValueError, match="Missing columns"):
        inspect_csv(bad)


def test_day_first_public_table_dates(tmp_path):
    data = ("Preface\nDate,SVENY05,SVENY07,SVENY10\n"
            "31-08-2026,4,4.2,4.4\n"
            "01-09-2026,4.1,4.3,4.5\n")
    path = tmp_path / "day_first.csv"
    path.write_text(data)
    frame = load_fed_curve_data(path, [5, 7, 10])
    assert str(frame.index[0].date()) == "2026-08-31"
    assert str(frame.index[1].date()) == "2026-09-01"


def test_mixed_dates_fail_loudly(tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text("Date,SVENY05,SVENY07,SVENY10\n2026-08-31,4,4,4\n01-09-2026,4,4,4\n")
    with pytest.raises(ValueError, match="Mixed or invalid"):
        load_fed_curve_data(path, [5, 7, 10])
