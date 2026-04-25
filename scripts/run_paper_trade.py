#!/usr/bin/env python3
"""Run paper trading workflow with explicit execution flag."""
from __future__ import annotations

import argparse
import logging

from src.config import PipelineConfig
from src.trading.ibkr_client import IBKRClient, IBKRSafetyFlags
from src.trading.order_builder import OrderTicket

from scripts.run_daily_signal import main as run_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
LOGGER = logging.getLogger("run_paper_trade")


def _print_tickets(tickets: list[OrderTicket]) -> None:
    for t in tickets:
        LOGGER.info("%s %s qty=%s dry_run=%s", t.instrument, t.action, t.quantity, t.dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-trading runner for Treasury fly strategy.")
    parser.add_argument("--execute-paper", action="store_true", help="Actually submit to paper account if all safety checks pass")
    args = parser.parse_args()

    cfg = PipelineConfig()
    run_signal()  # Always generate signal/report first.

    client = IBKRClient(cfg.ibkr_host, cfg.ibkr_port, cfg.ibkr_client_id)
    connected = client.connect()
    LOGGER.info("IBKR connected: %s", connected)
    LOGGER.info("Current positions: %s", client.get_positions())

    if not args.execute_paper:
        LOGGER.warning("Dry-run only. Use --execute-paper and safety flags to allow submission.")

    safety = IBKRSafetyFlags(
        dry_run=not args.execute_paper,
        allow_trading=cfg.allow_trading,
        paper_trading=cfg.paper_trading,
        live_trading=cfg.live_trading,
    )
    LOGGER.warning("Safety flags: %s", safety)
    client.disconnect()


if __name__ == "__main__":
    main()
