"""Generate descriptive rolling-factor diagnostics from actual Fed data."""
import argparse
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.data.fed_curve_loader import load_fed_curve_data
from src.research.pca_model import compute_yield_changes
from src.research.stability import stability_panel


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("feds200628.csv"))
    p.add_argument("--output", type=Path, default=Path("reports/factor_stability"))
    p.add_argument("--start", default="1990-01-01")
    a = p.parse_args()
    curve = load_fed_curve_data(a.data, [1, 2, 3, 5, 7, 10, 20, 30]).loc[a.start:].dropna()
    panel = stability_panel(compute_yield_changes(curve))
    a.output.mkdir(parents=True, exist_ok=True)
    panel.to_csv(a.output/"rolling_stability.csv", index=False)
    summary = panel.groupby(["window", "era"])[["pc1_cosine", "pc2_cosine", "pc3_cosine", "subspace_min_cosine", "pc1_variance"]].mean()
    summary.to_csv(a.output/"regime_summary.csv")
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for window, frame in panel.groupby("window"):
        axes[0].plot(frame["date"], frame["pc1_cosine"], label=str(window), linewidth=.6)
        axes[1].plot(frame["date"], frame["subspace_min_cosine"], label=str(window), linewidth=.6)
    axes[0].set_ylabel("PC1 absolute cosine")
    axes[1].set_ylabel("Minimum subspace cosine")
    axes[0].legend(title="Window (observations)")
    fig.tight_layout()
    fig.savefig(a.output/"stability.png")
    plt.close(fig)
    meta = {"source_sha256": hashlib.sha256(a.data.read_bytes()).hexdigest(),
            "first": str(curve.index.min().date()), "last": str(curve.index.max().date()),
            "observations": len(curve), "windows": [63,126,252],
            "investable_backtest": False, "publication_vintages_verified": False}
    (a.output/"metadata.json").write_text(json.dumps(meta, indent=2)+"\n")
    (a.output/"REPORT.md").write_text(
        "# Rolling factor stability\n\nDescriptive latest-vintage research only.\n\n"
        "![Stability](stability.png)\n\n"
        "See regime_summary.csv for mean consecutive-window alignment by calendar decade "
        "and estimation window. Decades are descriptive bins, not inferred market states. "
        "PC sign flips are removed; subspace angles also handle rotation within the top-three space. "
        "Nearby eigenvalues can exchange PC ranks. High daily alignment partly reflects heavily "
        "overlapping windows and is not predictive stability. Weekly publication times and revisions "
        "are not reconstructed. This report does not modify or supersede the existing negative "
        "transaction-cost findings.\n", encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
