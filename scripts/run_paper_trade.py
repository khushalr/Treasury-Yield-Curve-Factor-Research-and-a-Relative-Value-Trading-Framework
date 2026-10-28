#!/usr/bin/env python3
"""Run paper trading workflow with explicit execution flag."""
from __future__ import annotations

import argparse
import logging


from scripts.run_daily_signal import main as run_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
LOGGER = logging.getLogger("run_paper_trade")


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-trading runner for Treasury fly strategy.")
    parser.add_argument("--execute-paper", action="store_true", help="Intentionally rejected: account execution is not implemented")
    args = parser.parse_args()

    if args.execute_paper:
        parser.error("Paper order execution is disabled: contract, account and price verification are not implemented.")
    run_signal()
    LOGGER.info("Research-only dry run complete. No broker connection or order submission attempted.")


if __name__ == "__main__":
    main()
