# Resume and interview notes

## Defensible project entry (current public main branch)

**Treasury Yield Curve Factor Research & Relative-Value Backtesting | Python, pandas, NumPy, scikit-learn, pytest**

- Built a modular research pipeline using Federal Reserve Treasury fitted yields across eight maturities, estimating rolling PCA factors and constructing a PC1/PC2-hedged 5Y–7Y–10Y butterfly.
- Implemented prior-observation rolling z-score signals, DV01-normalized hypothetical exposures, and a cost-aware *retrospective synthetic* evaluation with explicit observation-lag and data-leakage tests.
- Added automated Python CI, deterministic offline test data, data-quality checks and fail-closed execution controls that prevent unverified brokerage orders.
- Developed research-only CUSIP selection, coupon valuation and bond DV01 analytics, comparing theoretical fitted-curve prices with government-account reference data while explicitly excluding execution and investment-return claims.

## What to show in an interview

1. Demonstrate the rolling factor-loading hedge equations and show a 5/7/10 loadings matrix.
2. Run the offline demo and explain why lagged targets differ from the same-day signal.
3. Compare summary.json at two different --cost-bp values; net P&L must not improve as costs rise.
4. Explain why a factor-neutral yield shock is neither tradable mispricing nor a verified arbitrage opportunity.
5. Be able to derive price change approximately as minus DV01 times yield change in basis points.
6. Explain the outstanding research: held-out years, actual instrument quotes, carry/funding and DV01 mapping.

**Do not quote a tradable Sharpe, return, win rate, trading profit, production execution system or live paper-trading record.** The current Fed daily observations were generally published weekly and historical fitted values may be revised; the two-observation lag does not reconstruct release-time data availability. Any reported P&L is synthetic sensitivity, not a funded strategy result.
