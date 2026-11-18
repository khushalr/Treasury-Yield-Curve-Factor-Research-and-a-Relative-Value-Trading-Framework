import numpy as np
import pandas as pd
import pytest
from src.research.availability import asof_vintages
from src.research.stability import loading_similarity, stability_panel


def test_delayed_release_and_revision():
    rows = pd.DataFrame({
        "observation_date": ["2025-01-02", "2025-01-02"],
        "available_at": ["2025-01-10", "2025-02-01"], "value": [4., 4.1]})
    result = asof_vintages(rows, ["2025-01-03", "2025-01-10", "2025-02-02"])
    assert np.isnan(result.iloc[0]["value"])
    assert result.iloc[1]["value"] == 4.
    assert result.iloc[2]["value"] == 4.1


def test_future_revision_cannot_change_past():
    rows = pd.DataFrame({"observation_date": ["2025-01-01"],
                         "available_at": ["2025-01-05"], "value": [4.]})
    before = asof_vintages(rows, ["2025-01-10"])
    future = rows.copy()
    future["available_at"], future["value"] = "2025-02-01", 99
    pd.testing.assert_frame_equal(before, asof_vintages(pd.concat([rows, future]), ["2025-01-10"]))


def test_sign_and_rotation_invariance():
    a = np.eye(4)[:, :3]
    c, subspace = loading_similarity(a, -a)
    assert np.allclose(c, 1) and subspace == pytest.approx(1)
    c, subspace = loading_similarity(a, a[:, [1, 0, 2]])
    assert c[0] == 0 and subspace == pytest.approx(1)


def test_stability_prefix_invariance():
    rng = np.random.default_rng(42)
    changes = pd.DataFrame(rng.normal(size=(50, 4)), index=pd.date_range("2025-01-01", periods=50))
    a = stability_panel(changes.iloc[:40], (10,))
    b = stability_panel(changes, (10,))
    pd.testing.assert_frame_equal(a, b.iloc[:len(a)].reset_index(drop=True))
