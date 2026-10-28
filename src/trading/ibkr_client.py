"""Safe wrapper around ib_insync for paper trading integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)

try:
    from ib_insync import IB, Contract, LimitOrder
except Exception:  # pragma: no cover - optional dependency
    IB = None
    Contract = Any
    LimitOrder = Any


@dataclass(slots=True)
class IBKRSafetyFlags:
    dry_run: bool
    allow_trading: bool
    paper_trading: bool
    live_trading: bool


def can_submit_order(safety: IBKRSafetyFlags, risk_passed: bool) -> tuple[bool, str]:
    """Evaluate strict gate conditions for paper-order submission."""

    if safety.live_trading:
        return False, "LIVE_TRADING=True is explicitly blocked."
    if safety.dry_run:
        return False, "Dry-run mode enabled."
    if not safety.allow_trading:
        return False, "ALLOW_TRADING=False."
    if not safety.paper_trading:
        return False, "PAPER_TRADING=False."
    if not risk_passed:
        return False, "Risk checks failed."
    return True, "Submission allowed (paper-only)."


class IBKRClient:
    """IBKR client with strict safety gate defaults."""

    def __init__(self, host: str, port: int, client_id: int) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB() if IB is not None else None

    def connect(self) -> bool:
        if self.ib is None:
            LOGGER.warning("ib_insync not installed; IBKR connection unavailable.")
            return False
        self.ib.connect(self.host, self.port, clientId=self.client_id)
        return self.ib.isConnected()

    def disconnect(self) -> None:
        if self.ib is not None and self.ib.isConnected():
            self.ib.disconnect()

    def get_positions(self) -> dict[str, float]:
        if self.ib is None or not self.ib.isConnected():
            return {}
        out: dict[str, float] = {}
        for p in self.ib.positions():
            out[p.contract.localSymbol or p.contract.symbol] = float(p.position)
        return out

    def qualify_contract(self, contract: Contract) -> Contract:
        if self.ib is None:
            return contract
        self.ib.qualifyContracts(contract)
        return contract

    def get_market_price(self, contract: Contract) -> float | None:
        if self.ib is None or not self.ib.isConnected():
            return None
        ticker = self.ib.reqMktData(contract)
        self.ib.sleep(1.0)
        return float(ticker.marketPrice()) if ticker.marketPrice() == ticker.marketPrice() else None

    def place_limit_order(
        self,
        contract: Contract,
        action: str,
        quantity: float,
        limit_price: float,
        safety: IBKRSafetyFlags,
        risk_passed: bool,
    ) -> Any:
        LOGGER.warning("ORDER REQUEST: action=%s qty=%s limit=%.4f", action, quantity, limit_price)
        allowed, reason = can_submit_order(safety, risk_passed)
        if not allowed:
            LOGGER.warning("ORDER BLOCKED: %s", reason)
            return None

        if self.ib is None or not self.ib.isConnected():
            LOGGER.warning("Not connected to IBKR. No order sent.")
            return None

        # Safety-critical: a port or user-set paper flag cannot verify account identity.
        # Do not submit until the account and contract/quantity/price paths are certified.
        LOGGER.error("ORDER BLOCKED: broker submission is intentionally not implemented.")
        return None

    def cancel_order(self, trade: Any) -> None:
        if self.ib is not None and trade is not None:
            self.ib.cancelOrder(trade.order)
