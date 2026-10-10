# Treasury Yield Curve Factor Research and a Relative-Value Trading Framework

## 1) What this project is (plain English)

This is my Treasury yield curve relative-value research project.

The core question is simple: if I model the curve structure with PCA, and then look at a 5Y–7Y–10Y butterfly, do temporary dislocations tend to mean-revert in a way that is useful for a disciplined signal process?

I am using Federal Reserve curve data for research, then turning that into a **paper-safe** daily signal pipeline.

---

## 2) The intuition I want to remember

If I come back to this six months from now, this is the mental model:

- The Treasury curve is not one number. It is a whole shape across maturities.
- Different maturities move together a lot, but not perfectly.
- PCA is my tool for summarizing the main movement patterns in that shape.
- Usually, I expect:
  - PC1 ≈ level,
  - PC2 ≈ slope,
  - PC3 ≈ curvature,
  but I should **always check this empirically** rather than assume it.
- A butterfly trade is trying to isolate relative richness/cheapness in the belly vs wings while hedging broader curve moves.
- In this project, 7Y is the belly and 5Y/10Y are the wings.

---

## 3) What data I use

Data source: Federal Reserve nominal yield curve dataset
https://www.federalreserve.gov/data/nominal-yield-curve.htm

Important context:

- It is daily **smoothed** Treasury curve data.
- It is great for research because it gives consistent tenors (like 5Y, 7Y, 10Y) over time.
- It is **not** the same thing as live tradable bond quotes.
- It is **not** intraday execution data.

So this is a research-quality signal input, not a direct execution feed.

---

## 4) Why I use yield changes (not levels) for PCA

I use daily yield changes because they are closer to the risk I care about.

- Yield levels are persistent and drift through regimes.
- PCA on levels can become mostly a decomposition of historical rate regimes (high-rate era vs low-rate era), which is not exactly the same as day-to-day hedging risk.
- PCA on daily changes is more about **how the curve moves** right now.

For this project’s purpose (relative-value dislocations + hedging intuition), daily changes are the more useful object.

---

## 5) Rolling PCA and look-ahead bias

I fit PCA in a rolling historical window.

Key rule: at date `t`, the model should only use information that was available **before** trade execution at `t`.

Why this matters:

- Look-ahead bias means accidentally letting future information leak into the signal.
- In plain terms: it makes backtests look smarter than they really would have been live.

This repo includes basic historical-alignment tests; an audited execution-price backtest is not yet available.

---

## 6) The 5Y–7Y–10Y butterfly in this project

What the fly means here:

- 5Y and 10Y are wings.
- 7Y is the belly.
- “Long belly” means overweighting the 7Y leg versus wings.
- “Short belly” means the opposite.

I try to solve fly weights that are neutral (as much as possible) to PC1 and PC2.

Intuition:

- If PC1 and PC2 are hedged out, what remains is less “broad market move” and more “relative shape dislocation.”
- I interpret that residual as the mispricing signal candidate.

Important: this is a **synthetic research fly**, not automatically a directly tradable package.

---

## 7) Signal construction

Signal flow:

1. Compute fly residual value.
2. Standardize into a z-score.
3. Use mean-reversion direction in this code: signal is based on `-z`.

Alignment detail I care about:

- The z-score uses prior-history rolling mean/std (`shift(1)` logic), not same-day information.

Trade-direction convention used in this code:

- High positive z-score → short fly.
- Very negative z-score → long fly.
- Inside entry threshold → signal is explicitly zero (no new trade).

I also cap signal magnitude to prevent runaway sizing.

---

## 8) Risk and sizing

Sizing is expressed in abstract DV01 space.

- DV01 = approximate dollar value change for a 1bp move in yield.
- Here it is used as a risk-normalized exposure unit, not as broker-native quantity.

Risk controls include:

- signal capping,
- gross/leg DV01 caps,
- position-change caps,
- stale/missing data checks,
- paper-only/live-block checks,
- order-path safety checks.

This separation is intentional: model risk intent first, instrument execution mapping second.


---

## 9) Backtesting realism checks I still care about

These are the practical things that can make a nice research signal look worse in reality:

- lagged signals to avoid accidental look-ahead
- volatility scaling so risk is not regime-dependent by construction
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

**Research integrity caveat:** This model currently standardizes daily changes in a dynamically weighted synthetic fly, not a consistently defined valuation spread. Its abstract DV01 intents do not represent tradable shares or validated P&L. A point-in-time walk-forward backtest with explicit costs and execution timing is necessary before publishing performance claims.

### Trading modes

- `paper_synthetic`: synthetic exposure only, no IBKR order submission.
- `etf_proxy`: blocked pending ETF DV01 calibration, share conversion, and duplicate-symbol netting.
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

To request execution-mode validation (the current runner **does not submit orders**), pass:

```bash
python scripts/run_paper_trade.py --execute-paper
```

This runner does not implement order submission. Missing market-spread data fails closed in the risk-check layer.

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
