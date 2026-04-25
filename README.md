# Treasury Yield Curve Factor Research and a Relative-Value Trading Framework

This is a research project exploring U.S. Treasury yield curve dynamics using rolling principal component analysis (PCA), then testing whether factor-neutral curve dislocations can support a relative-value trading framework.

This project has two goals:

1. understand the economic structure of the Treasury curve through level, slope, and curvature factors;
2. evaluate whether those factor insights can be turned into a realistic trading signal once delays, volatility targeting, and transaction costs are considered.

## Why this project matters

The Treasury yield curve is one of the most important objects in macroeconomics, fixed income, and systematic trading. Instead of treating each maturity as a separate time series, this project studies the curve as a structured object driven by a small number of common factors.

The research asks two linked questions:

- Can rolling PCA recover the classic level / slope / curvature interpretation of the Treasury curve?
- After removing common factor exposure, do residual relative-value dislocations contain enough signal to support a tradable strategy?

## Main findings

- The Treasury curve is highly low-dimensional: the first few principal components explain the vast majority of daily curve variation.
- The first three components align closely with the classic economic interpretation of:
  - **Level**: the whole curve shifts up or down
  - **Slope**: the front end and long end move differently
  - **Curvature**: the belly moves differently from the wings
- A naive relative-value backtest can appear promising.
- Once more realistic assumptions are added — such as signal delay, volatility targeting, and transaction costs — performance weakens materially.
- The main conclusion is that **factor structure is strong, but extracting robust trading edge is much harder than a simple in-sample backtest suggests**.

## Project overview

The workflow is:

1. Load Treasury curve data across maturities.
2. Convert the data into a clean panel of yield changes.
3. Estimate rolling PCA to study how curve factors evolve through time.
4. Interpret the leading components economically.
5. Build a relative-value signal from residual curve dislocations.
6. Backtest both a naive and a more realistic implementation.
7. Compare performance under progressively stricter assumptions.

## Methods

### 1. Yield curve factor extraction
Rolling PCA is applied to changes in Treasury yields across maturities. This allows the project to estimate the dominant modes of curve movement over time rather than assuming a fixed covariance structure for the full sample.

### 2. Factor interpretation
The leading components are interpreted through their loading shapes:

- **PC1**: broad parallel shift of the curve
- **PC2**: steepening vs flattening
- **PC3**: curvature or belly-vs-wings movement

### 3. Relative-value construction
Using the factor model, the framework looks for curve segments whose movement is unusually rich or cheap relative to the common factor structure. This motivates a factor-aware relative-value signal.

### 4. Backtesting
The strategy is evaluated under increasingly realistic assumptions, including:

- lagged signals to avoid lookahead bias
- volatility scaling
- transaction costs / spread assumptions
- out-of-sample style evaluation logic

## Production-style daily pipeline (paper-safe)

This repo now includes a modular `src/` pipeline that converts the research idea into a daily signal workflow designed for **safe paper-trading experimentation only**.

### Strategy summary

- Use Fed nominal Treasury curve data.
- Compute daily yield changes.
- Fit rolling PCA (historical window only, no look-ahead).
- Build a 5Y–7Y–10Y fly approximately neutral to PC1/PC2.
- Standardize fly residual into a z-score using only prior-history rolling moments (no same-day leakage).
- Use mean reversion signal (`position = -z_score`, clipped by risk limits).
- Convert signal into abstract DV01 exposures before any instrument mapping.

### Why this is not directly tradable as-is

The core model operates on synthetic curve points, not executable exchange or OTC instruments. A separate instrument mapping layer is required to translate abstract tenor DV01 targets into tradable proxies/contracts/cash bonds.

### Trading modes

- `paper_synthetic`: synthetic exposure only, no IBKR order submission.
- `etf_proxy`: configurable ETF proxy mapping for paper testing.
- `futures_proxy`: planned extension (requires contract roll + DV01 mapping).
- `cash_treasury`: planned extension (requires CUSIP selection + bond analytics).


### Environment setup and tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Run checks:

```bash
python -m compileall src scripts tests
pytest -q
```

Notes:
- `numpy`, `pandas`, and `scikit-learn` are the core runtime requirements.
- `pytest` is required for the automated test suite.
- `ib_insync`, `matplotlib`, and `jupyter` are optional extras and are not required for core tests.

### Running the daily signal

```bash
python scripts/run_daily_signal.py
```

This computes signals, sizes positions, proposes orders, runs risk checks, and writes reports (`md/csv/json`) under `reports/`.

### Running paper-trading dry run

```bash
python scripts/run_paper_trade.py
```

To allow paper submission, pass:

```bash
python scripts/run_paper_trade.py --execute-paper
```

Even with that flag, order placement remains blocked unless safety flags and risk checks pass.

### Connecting to IBKR paper TWS/Gateway

Defaults in `src/config.py`:

- host: `127.0.0.1`
- port: `7497` (paper)
- client ID: configurable (`IBKR_CLIENT_ID`)

Keep `ALLOW_TRADING=False` and `LIVE_TRADING=False` unless intentionally testing with controls in place.

### Safety warnings

- Default behavior is dry-run and paper-only.
- Live trading is blocked by default.
- No market orders are generated by default order builder.
- Risk checks gate the workflow before order sizing/ticketing and again before any submission attempt.

### Known limitations

- Fed curve data is delayed and not intraday executable market data.
- Synthetic yield relationships differ from tradable securities.
- Cash Treasury implementation still needs: CUSIP selection, liquidity checks, accrued interest treatment, and shorting/financing assumptions.
- Futures implementation still needs: contract roll logic and robust DV01 mapping.
- Backtest and research performance can degrade materially after costs, slippage, and execution constraints.
