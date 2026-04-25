# Trading Safety Gates

This project is intentionally configured to prevent accidental live trading.

## Default safety configuration (`src/config.py`)

- `ALLOW_TRADING = False`
- `PAPER_TRADING = True`
- `LIVE_TRADING = False`
- `DRY_RUN = True`

These defaults mean strategy runs produce signals and proposed tickets, but do not submit executable orders.

## Execution gating in IBKR client

`src/trading/ibkr_client.py` blocks order submission unless **all** conditions are true:

1. `dry_run` is `False`
2. `allow_trading` is `True`
3. `paper_trading` is `True`
4. `live_trading` is `False`
5. risk checks pass

If any condition fails, orders are blocked and a warning is logged.

## Risk checks before order flow

`src/trading/risk_checks.py` enforces checks including:

- data freshness
- signal date alignment
- required tenor availability
- entry threshold
- gross and leg DV01 caps
- order size cap
- paper-only mode and no live mode
- bid/ask spread guard (when available)
- daily loss guard

`scripts/run_daily_signal.py` runs risk checks before order-ticket generation and again afterward.
If pre-risk checks fail, no order tickets are generated.

## Order-type safety

`src/trading/order_builder.py` creates `LMT` order tickets by default (not market orders).

## Optional IBKR dependency

`ib_insync` is optional for research/testing.
Core signal/research tests do not require an active IBKR connection.
