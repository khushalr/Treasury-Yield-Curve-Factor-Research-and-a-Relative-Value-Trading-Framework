# Safety model: research only, no broker submission

The default mode is synthetic research with no brokerage activity. No configuration switch in the provided runners enables executable order submission.

- scripts/run_daily_signal.py calculates an as-of research signal and report; it produces **no broker tickets**, even if hypothetical risk checks otherwise pass.
- scripts/run_paper_trade.py produces a report without connecting to IBKR. Its --execute-paper argument is rejected.
- src/trading/order_builder.py refuses dry_run=False. Dry-run tickets (if called explicitly) are **illustrative abstract exposures**, not valid share or bond quantities.
- src/trading/instrument_mapper.py supports nontradable synthetic labels only. ETF mapping is disabled until dollar DV01 is measured per actual instrument and duplicate ticker exposures are aggregated.
- src/trading/ibkr_client.py has an explicit unconditional no-submission guard. Passing paper flags is not enough to prove a connected account is paper only.
- LIVE_TRADING is disabled by default; this project does not contain a live-order workflow.

**Do not copy these research DV01 numbers into broker order quantity fields.** ETF shares, futures contracts and cash Treasury face amounts require different analytics and verified market data.

A future paper integration would need independently testable account-type verification, market/limit prices and spreads, qualified contracts, tick sizes, true instrument DV01, order confirmation, exposure aggregation, financing, kill switches and recorded fills. None are implemented or claimed here.
