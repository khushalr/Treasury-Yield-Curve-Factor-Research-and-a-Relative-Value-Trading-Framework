# Treasury Yield Curve Factors & Relative-Value Research

**Rolling PCA · PC-hedged 5Y/7Y/10Y butterfly · causal mean-reversion signals · cost-aware synthetic backtest · fail-closed safety**

A fixed-income quantitative research project that asks: **can unusual movements in the 7-year section of the U.S. Treasury yield curve predict subsequent curve changes, after lagging the signal and charging stylized turnover costs?**

This repository contains a reproducible Python research pipeline, not an executable trading strategy or a claim of realized profits. Its inputs are **Federal Reserve smoothed fitted yields**, which are not tradeable bond quotes.

## What it demonstrates

| Area | Implementation |
| --- | --- |
| Fixed-income data engineering | Load Federal Reserve nominal fitted-yield CSV, parse metadata, validate dates and maturities |
| Factor research | PCA on daily yield changes across **1, 2, 3, 5, 7, 10, 20 and 30 years** |
| Relative value | Construct a **5Y–7Y–10Y** fly with fitted PC1/PC2 factor neutrality |
| Statistical signals | Rolling, prior-history z-scores, thresholded mean-reversion hypothesis |
| Hypothetical risk | DV01-weighted exposures, volatility scaling, gross/leg caps |
| Evaluation | Two-observation execution lag, daily DV01 P&L approximation, configurable turnover costs |
| Engineering | Deterministic offline demo, unit/regression tests, Python 3.11/3.12 GitHub Actions |
| Safety | **No broker orders can be submitted**; there is no certified contract, account or price mapping |

## Quick start: reproduce without credentials or network access

Requires Python 3.11+ and runs from the repository root.

~~~bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

python -m pytest -q
python -m scripts.generate_demo_data

# Walk-forward backtest on clearly SYNTHETIC, deterministic data
python -m scripts.run_backtest --data data/demo_curve.csv \
    --pca-window 60 --signal-window 20 --entry-z 1.0 \
    --cost-bp 0.5 --output reports/demo_backtest

# Latest signal as of the last synthetic observation (not "today")
python -m scripts.run_daily_signal --data data/demo_curve.csv \
    --as-of 2025-12-31 --pca-window 60 --signal-window 20 \
    --output reports/demo_signal
~~~

On Windows PowerShell, enter each command on one line (the backslashes above are Unix shell continuations). Outputs are written into ignored directories under reports/. The generator always uses a fixed seed and marks its data as synthetic.

Backtest files:
- reports/demo_backtest/daily_backtest.csv: time-series signals, target/held DV01, turnover, cost and P&L sensitivity.
- reports/demo_backtest/summary.json: time span, active days, hypothetical gross/net P&L, illustrative Sharpe and maximum drawdown.
- reports/demo_signal/daily_report_YYYYMMDD.{json,csv,md}: signal and explicitly blocked risk gates.

**No performance statistics are hard-coded into this README.** Run the script on a documented dataset and inspect actual results, including negative results, before quoting any number.

## Use the included historical Fed dataset

A Federal Reserve nominal yield curve CSV is included as feds200628.csv. Its freshness is **not** asserted; check the latest date yourself. Re-run research using:

~~~bash
python -m scripts.run_backtest --data feds200628.csv \
    --pca-window 504 --signal-window 126 \
    --entry-z 2.5 --cost-bp 0.5 --output reports/fed_historical
~~~

The 504-observation window is slower but reduces noise versus a short example window. If you want an as-of daily *research* report from a known historical date, specify --as-of. A default daily run checks whether data are fresh and reports a blocked risk gate when they are not.

Original data source: [Federal Reserve — Nominal Yield Curve Data](https://www.federalreserve.gov/data/nominal-yield-curve.htm). The fitted points are model-derived nominal Treasury yields; they do not include the observed bid/ask, bond-specific DV01, carry or funding.

## Methodology at a glance

1. Take first differences of fitted yields (in percentage points) rather than PCA on yield levels. Estimate rolling PCA across eight maturities.
2. For date t, use **only loadings fitted strictly before t** to solve a three-leg fly with 7Y yield weight +1 and approximately zero exposure to PC1/PC2. Refuse ill-conditioned hedge matrices.
3. Define the daily yield-fly **shock** as weights times that day's 5Y/7Y/10Y yield changes. Compare the shock with a mean/std built from **prior shocks only**.
4. Hypothesize reversal after extreme shocks: positive z means short the **yield-fly**; negative z means long the yield-fly. Below the threshold, target exposure is **exactly zero**. This is a *hypothesis*, not proven persistent mispricing.
5. Convert signal direction into **hypothetical bond-price DV01** (opposite sign to yield exposure); scale all legs uniformly for caps so their relative hedge weights survive.
6. For diagnostic evaluation, shift hypothetical targets by **two observations** before applying them to further changes in fitted yields. Deduct turnover times a configurable **yield-bp-equivalent cost**. P&L is in illustrative DV01-dollars, **not return on capital**.

For definitions, leakage controls, cost assumptions, and known caveats, read [Methodology](docs/METHODOLOGY.md).

## Project layout

~~~text
src/data/             Fed CSV loading and validation
src/research/         Rolling PCA, fly construction, signal generation, backtest
src/trading/          Abstract position sizing and fail-closed execution stubs
src/reporting/        Markdown, JSON and CSV signal reports
scripts/              Reproducible CLI runners and synthetic fixture generator
tests/                Leakage, threshold, sizing, safety and P&L cost tests
docs/                 Methodology, safety rules, resume/interview notes
.github/workflows/    Automated test matrix and example reproducibility run
fed_data_analysis.ipynb    Historical exploratory notebook (legacy research)
~~~

## Interpretation and limitations

A shock in **daily fitted yields** need not indicate an attractive trade in cash Treasuries. Real-world implementations would require actual security selection and bond pricing, accrued interest, financing/repo, bid/ask, carry, convexity, roll/down and short availability. The PCA also changes across regimes. Backtest statistics on synthetic exposures can be economically meaningless when those effects are absent.

**There is no production or live-trading path.** The paper runner is a no-connection dry-run; passing an execution flag raises an error. Even the IBKR client is hard-blocked from submitting orders. See [Safety](docs/SAFETY.md).

### Research questions worth extending

- Do findings persist on held-out calendar regimes, especially inflation and hiking cycles?
- Does a simple 2×wing minus belly yield butterfly outperform factor-hedged shocks?
- How sensitive are conclusions to transaction-cost assumptions and execution delay?
- Can cash bonds or futures be mapped to calibrated dollar DV01 without conflating tenors or tickers?

Resume-safe project wording is in [Resume Notes](docs/RESUME_NOTES.md); only describe demonstrated functionality and measured results.
