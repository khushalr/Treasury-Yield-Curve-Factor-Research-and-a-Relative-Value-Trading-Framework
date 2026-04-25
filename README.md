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

This repo includes tests to guard against that.

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
- Inside entry threshold → no new trade.

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

## 9) Why this is not directly live-tradable

Honest version:

- Fed data gives clean research tenors, not live tradable bond objects.
- Real implementation needs instrument mapping (CUSIPs, futures contracts, etc.).
- A 5Y–7Y–10Y fly is not directly equivalent to a standard Treasury futures fly because there is no clean 7Y futures contract.

For futures implementation, I still need:

- contract selection,
- roll logic,
- CTD / conversion-factor-aware risk mapping,
- proper futures DV01.

For cash-Treasury implementation, I still need:

- CUSIP universe logic,
- accrued interest handling,
- liquidity filters,
- financing/shorting assumptions.

---

## 10) Paper-trading architecture (intended flow)

Fed data signal → abstract DV01 target → instrument mapping → IBKR paper market data → proposed order tickets → safety checks → optional paper-only limit orders.

What is true by default:

- dry-run mode is on,
- live trading is blocked,
- market orders are not used by default,
- this is research/learning infrastructure, not a claim of edge.

---

## 11) Repository structure (teaching view)

- `src/research/`
  - Where the model logic lives: yield changes, rolling PCA, fly construction, residual/z-score signal.
- `src/trading/`
  - Bridge from model outputs to paper-trading concepts: sizing, mapping, tickets, risk gates, IBKR wrapper.
- `src/data/`
  - Fed curve loader and validation checks.
- `src/reporting/`
  - Daily report generation (`md/json/csv`) so I can inspect what happened each run.
- `scripts/`
  - Entry points I can run directly.
  - `run_daily_signal.py` is the main non-execution daily workflow.
  - `run_paper_trade.py` is paper-trading workflow wiring.
- `tests/`
  - Guardrails so I do not accidentally reintroduce look-ahead bias or unsafe execution behavior.
- `docs/SAFETY.md`
  - Consolidated safety gates and defaults.
- `fed_data_analysis.ipynb`
  - Canonical exploratory notebook for this research.

---

## 12) How to run

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run checks:

```bash
python -m compileall src scripts tests
pytest -q
```

Run daily signal pipeline:

```bash
python scripts/run_daily_signal.py
```

Optional paper workflow:

```bash
python scripts/run_paper_trade.py
python scripts/run_paper_trade.py --execute-paper
```

IBKR note:

- IBKR connection requires TWS or IB Gateway paper account running locally.
- There is currently **no** `scripts/run_ibkr_futures_dry_run.py` in this repo.

---

## 13) Safety notes (read this before touching anything)

This project should never place live trades by default.

Safety flags (see `src/config.py`):

- `ALLOW_TRADING`
  - Master permission flag. If `False`, execution is blocked.
- `PAPER_TRADING`
  - Must be `True` for any paper submission path.
- `LIVE_TRADING`
  - If `True`, submission is explicitly blocked by safety logic.
- `DRY_RUN`
  - If `True`, do not submit orders; only generate proposals.

Current defaults are intentionally conservative:

- `ALLOW_TRADING=False`
- `PAPER_TRADING=True`
- `LIVE_TRADING=False`
- `DRY_RUN=True`

Also: order tickets default to limit orders (`LMT`), not market orders.

---

## 14) What I still need to improve (learning roadmap)

- Check PCA stability through time (do factors stay interpretable?).
- Compare 5Y–7Y–10Y vs futures-native alternatives like 2Y–5Y–10Y or 5Y–10Y–30Y.
- Add proper futures DV01 mapping using CTD + conversion factors.
- Add robust contract roll handling.
- Add transaction cost and slippage assumptions.
- Add stronger out-of-sample protocol.
- Improve reporting/plot diagnostics.
- Add monitoring for when PCA factors stop behaving like level/slope/curvature.

---

## 15) Honesty statement

I do **not** claim this is profitable.

I also do **not** claim this is production-ready live trading infrastructure.

Paper results are not live results.

This repository is for research, learning, and building safer process discipline.
