# Methodology, Assumptions and Reproducibility

## Research hypothesis and scope

The testable hypothesis is that an unusually large *daily change* in a factor-hedged 5Y/7Y/10Y fitted-yield butterfly is followed by an opposite move. This is *not* a cointegration test of butterfly levels and it does not establish mispricing relative to cash instruments. Daily shock reversion may be a weak or nonexistent effect.

The input is the Fed fitted **nominal** Treasury curve. Yield columns SVENY01, SVENY02, etc. are in percent, so 0.01 percentage points = 1 basis point. **The Fed generally publishes the daily observation series once per week, typically Tuesday through the prior Friday, and historical observations may be revised.** A date-indexed delay of two observations is not a valid proxy for the public release schedule. Results from this code are deliberately retrospective and synthetic, **not point-in-time investable performance**. Source: https://www.federalreserve.gov/data/nominal-yield-curve.htm

## Factor extraction

For the ordered tenor panel 1/2/3/5/7/10/20/30Y, define dY(t) = Y(t)-Y(t-1). In a rolling window ending at t, scikit-learn PCA estimates an orthogonal loading matrix. The decomposition uses centered changes and is not standardized to unit variance across tenors; this is intentional because bps are a common risk scale. Inspect signs and explained variance; PC1/2/3 need not perfectly equal level/slope/curvature.

For the fly observed on t, use PCA loadings fitted on the latest available observation strictly earlier than t. With belly weight w7=1, solve the two linear equations:
- w5 * PC1_5 + PC1_7 + w10 * PC1_10 = 0
- w5 * PC2_5 + PC2_7 + w10 * PC2_10 = 0

Skip ill-conditioned systems and hedge weights above the stability cap. PC factor neutrality is a *loading exposure*, not key-rate DV01 or convexity neutrality.

## Shock signal

Define shock(t) = w5(t)*dY5(t) + dY7(t) + w10(t)*dY10(t). The z-score uses a mean and standard deviation calculated over shock values **strictly prior** to t. Today's shock affects the numerator only. With z > entry threshold: short the yield fly; z < negative threshold: long the yield fly. With insufficient history, zero variance or a threshold miss, signal/exposure is zero.

The fly's hedge weights change over time. Earlier shocks may therefore use earlier hedges; rolling historical moments mix these hedge definitions. This is explicitly a *dynamic hedged-shock study*, not the mark-to-market of one static security portfolio.

## Synthetic sensitivity accounting

Hypothetical positions are expressed in **dollars of DV01 per bp** (positive DV01 means bond prices benefit when yields fall). The signal sign is inverted when converting yield-fly direction into bond-price DV01. Per-leg DV01 limits scale the entire hedge, not independent legs.

For day t, define held_DV01(t) = target_DV01(t-2). This observation lag separates same-row signals and P&L; it **does not correctly model the weekly publication timing**. It is a stylized retrospective diagnostic, not an implementation assumption. The daily sensitivity is:

    gross_pnl(t) = -sum_over_legs[held_DV01_i(t) * (dY_i(t) * 100)]
    cost(t) = cost_bp * sum_over_legs[abs(held_DV01_i(t) - held_DV01_i(t-1))]
    net_pnl(t) = gross_pnl(t) - cost(t)

Here cost_bp represents an **assumed yield-bp-equivalent charge on traded dollar DV01**, not actual historical spread observations. It can be stress-tested with --cost-bp. The code does not estimate execution slippage or funding.

The backtest reports net cumulative *DV01-dollars* and an illustrative annualized Sharpe based on daily net sensitivity (252 sessions/year). **No denominator capital, leverage financing, coupon accrual, realized instrument prices, or exchange execution is modeled**, so this is not a portfolio return or a verified investment Sharpe ratio.

## Look-ahead controls and what remains

- Rolling PCA weights used for today's shock are estimated strictly before today.
- Rolling z-score reference mean and std are shifted one observation.
- Position targets are delayed two *observation rows* before being applied to changes. This is a partial anti-leakage check only; data release timestamps are not reconstructed.
- Tests perturb an observation at the sample end and assert earlier backtest outputs remain unchanged.
- Tests assert transaction costs can only reduce simulated net P&L.

**Further controls needed before any real trading claim:** timestamp-level availability of published Fed observations, a point-in-time constituent universe, walk-forward hyperparameter selection and held-out years, holidays and nonsynchronous pricing, realistic DV01 and financing curves, instrument bid/ask/volume, and broker-account verification.

No strategy performance, accuracy or trading profitability is claimed by the implementation alone.
