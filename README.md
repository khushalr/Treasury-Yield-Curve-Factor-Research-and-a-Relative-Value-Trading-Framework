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


## Reproducible synthetic research backtest

Run from the repository root after installing `requirements-dev.txt`:

```bash
python -m scripts.run_backtest --data feds200628.csv
python -m pytest -q
```

Outputs: `reports/backtest/synthetic_backtest_daily.csv` and `reports/backtest/synthetic_backtest_summary.json`. Costs default to **0.25 bp of yield per unit of absolute DV01 traded, one-way**, an illustrative assumption, not a measured bond spread.

The research backtest uses daily Fed smoothed fitted zero-coupon curve yields for 5Y/7Y/10Y. PCA is fitted strictly on past daily yield changes; the belly/wing yield combination is standardized against preceding yield levels with the *same* historical loadings applied consistently across the window. A signal generated using day `t` yield data is **executed hypothetically at t+1's smoothed curve mark** and starts earning P&L thereafter. Position size is normalized to **one dollar per yield-basis-point of gross DV01**, and synthetic P&L is the first-order duration approximation `-sum(DV01_tenor × delta_yield_bp)`. This does not represent a percentage return, portfolio Sharpe ratio, cash-bond backtest, or executable strategy.

The reported `unit_pnl_sharpe_not_roi` measures the annualized mean/stdev of **synthetic unit-DV01 P&L**, not an investable strategy Sharpe. An apparent chronological holdout is **not** truly out of sample if researcher decisions were informed by this history. The data are smoothed and can be revised; dates are model observation dates, not tradable market closes. There is no coupon/carry/roll-down, convexity, CUSIP selection, repo financing, exact price/quote matching, bid/ask spread measurement, taxes or capital budgeting.

Regression tests use explicitly synthetic data, not the actual Fed file. **No validated empirical performance or profitable strategy is claimed.** Do not use this research backtest for execution or advertising investment performance.


## Automated data refresh

The Fed fitted nominal yield curve is generally **published weekly**, typically Tuesday (covering through the previous Friday), rather than updated every market day. [Official source](https://www.federalreserve.gov/data/nominal-yield-curve.htm).

Use `python scripts/update_fed_data.py` to download and validate the full `feds200628.csv` source. It checks required 5Y/7Y/10Y columns, parses the Fed's day-month-year observation dates explicitly, rejects duplicate/non-monotonic dates, and refuses a regressing or unexpectedly shrinking download. It atomically replaces the file only after validation. Since Fed staff can revise past values, a changed CSV is not necessarily just appended new observations.

GitHub Actions workflow `.github/workflows/refresh-fed-data.yml` refreshes **Wednesdays 17:30 UTC** (or on manual dispatch). When changed, it commits the updated CSV using the GitHub Actions bot. Scheduled workflows run from GitHub's **default branch**, so the automatic refresh begins only after this draft PR is validated and merged. In repository Settings → Actions → General, ensure Actions have read/write `contents` permission. Review weekly diffs for unexpected revisions. The workflow will fail rather than overwrite malformed data.

**Tradeable implementation:** The 5Y/7Y/10Y series are theoretical fixed-maturity yields, not CUSIPs, ETF shares or a 3-leg futures spread. A realistic research-to-trading bridge would select specific 5Y, 7Y and 10Y cash Treasury CUSIPs (preferably appropriately seasoned off-the-run notes), compute actual prices, dollar DV01 and possible convexity/financing effects, hedge level and slope in dollar DV01, then use borrowable bonds, executable bid/ask and financing rates. A model overweighting the 7Y belly and underweighting the wings requires long and short exposures; spot bond positions cannot be assumed accessible at retail. There is no single listed exchange-traded instrument that exactly reproduces this modeled fly. **No live order submission should be enabled based on the current smoothed Fed series.**

 
## CUSIP-level cash Treasury *research-only* paper workflow

The model's tenor exposures are NOT direct instruments. The closest approach is three **distinct cash Treasury note CUSIPs** with remaining maturities near 5, 7 and 10 years, respectively. The 7Y candidate may have been issued as a 10-year note originally. No current CUSIPs or dealer quotes are hardcoded or fabricated.

1. Fetch historical auction identifiers/metadata from the U.S. Treasury Fiscal Data API (requires internet):

   `python -m scripts.fetch_treasury_auctions --as-of 2026-10-09`

2. Obtain a *separate*, attributable **same-date** two-sided clean-price quote CSV from a market-data provider or broker with headers:

   `as_of,cusip,bid_clean,ask_clean,source`

   Every quoted price must be per **$100 par**, source-tagged and for the exact valuation date. Do not use invented quotes for a real output. No brokerage quote collection is implemented.

3. With a Fed dataset containing the *same date* and all SVENY01–SVENY30 yields, run:

   `python -m scripts.run_cash_treasury_paper --as-of 2026-10-09 --quotes-file data/verified_cash_quotes.csv --direction 1 --gross-dv01 100`

   Direction `+1` means hypothetical **buy 7Y / sell 5Y and 10Y**; `-1` reverses that. `0` means flat. The CLI requires a manually supplied direction intentionally: translating the rolling synthetic PCA signal into a cash-bond trade is *not yet validated*. The output is a **non-executable research report**, not a broker instruction.

**How it works:** Selects aged notes with remaining maturities near target tenors; projects semiannual coupons; solves an approximate clean-price YTM; computes finite-difference dollar DV01 and model clean values from a linearly interpolated Fed fitted zero curve; builds approximate level and linear-maturity-slope neutral dollar-DV01 weights; converts each target into *rounded hypothetical par amounts*. It reports a descriptive model-minus-market-price difference and an indicative half-spread entry cost. The model gap does not establish profit or arbitrage.

**Still missing for any real trade:** authoritative reference-data validation for reopenings and coupon quirks, proper settlement/accrual and ex-coupon handling, dealer executable bid/ask depth, bond availability and short borrow, repo/financing, key-rate/PC hedge matching, dynamic CUSIP roll, historical point-in-time data vintages, actual cost-aware bond backtesting, and independent review of corporate and operational risks. The code has **no live-trading bridge**.

Local offline tests are synthetic fixtures only, not evidence of actual historical or realizable returns.


## Independent auction-price calibration (October 2026 audit)

A pricing audit identified and corrected a material bug in `clean_price_from_ytm`: the semiannual discount factor was incorrectly raised to twice the number of semiannual coupon periods. With `(1 + y/200)^(-periods)` instead, newly issued September 2026 Treasury note benchmarks reproduce reported auction prices to about 0.001 price points per $100 par:

| Term | Issue/maturity | Coupon | Auction YTM | Published auction price | Model clean price |
|---|---|---:|---:|---:|---:|
| 5 years | 2026-09-30 / 2031-09-30 | 5.000% | 5.033% | 99.856 | 99.855714 |
| 7 years | 2026-09-30 / 2033-09-30 | 5.000% | 5.085% | 99.505 | 99.504596 |

Benchmark source: U.S. Treasury auction-result announcements, September 2026. Tests: `tests/test_cash_treasury.py`. These are primary-auction pricing sanity checks, **not secondary-market bid/ask validations, strategy returns or evidence of alpha**. Settlement assumptions remain simplified; no verified three-security historical panel or backtest using independently observed clean bond quotes is available.

**Validation blocker:** The execution environment cannot directly download the official Treasury auction catalog or historical CUSIP-level broker bid/ask prices. Until such records are supplied, the project must not report live relative-value gaps or cash-bond investment performance. Verify source coupon/price rows independently before publishing these benchmarks as external evidence.


## Historical CUSIP reference-price research dataset

A **new** official-source importer provides per-CUSIP daily FedInvest reference prices:

```bash
python -m scripts.fetch_fedinvest_prices --start 2025-01-01 --end 2025-03-31
```

The command downloads pages from the U.S. Treasury Fiscal Data `fip_rates_prices` endpoint, checks note CUSIPs, observation dates, duplicate quotes, and positive buy/sell/EOD fields, then writes `data/fedinvest_reference_prices.csv`. It preserves source URLs and explicitly labels columns as **reference**, not executable price. Keep the data out of `src/research/cash_treasury.read_quotes()`: that method requires genuinely observed and attributable dealer bid/ask clean prices.

The `src/data/fip_prices.py:prepare_reference_panel` helper matches these references to the exact-date Fed curve, an as-of auction CUSIP universe, and derived theoretical bond values (complete 5Y/7Y/10Y sets only). Its output describes **indicative model-versus-government-account reference gaps, not tradable arbitrage or backtest P&L**. Missing dates/CUSIPs fail closed and are listed separately; no price forward filling.

**Critical research caveats:** FedInvest prices support government-account transactions/redemptions and daily valuations; they are not guaranteed dealer executable quotes or consistent closing marks. The Fed fitted Treasury yield series is smoothed and can be revised. Historical CUSIP selection, issue/reopening metadata and timing must be validated separately. Realistic bond strategy P&L requires point-in-time bond pricing, coupon accrual, sale/short borrow and financing, roll conventions and spreads. Historical API acquisition was not completed in the assistant execution environment due to outbound network DNS restrictions, so **no numeric actual historical backtest statistics are verified here**.

Source: [U.S. Treasury Fiscal Data API, FedInvest Rates and Prices](https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/fip_rates_prices).
