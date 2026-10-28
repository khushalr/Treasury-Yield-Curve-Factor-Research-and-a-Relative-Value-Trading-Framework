"""Build human-reviewable order tickets from target exposures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrderTicket:
    instrument: str
    action: str
    quantity: float
    estimated_price: float | None
    order_type: str
    reason: str
    signal_date: str
    dry_run: bool = True


def build_order_tickets(
    target_positions: dict[str, float],
    current_positions: dict[str, float],
    signal_date: str,
    min_trade_size: float = 1.0,
    max_allowed_trade: float = 250.0,
    dry_run: bool = True,
) -> list[OrderTicket]:
    """Create tickets from diffs between current and target positions."""

    if not dry_run:
        raise ValueError("Order builder is research-only: no validated prices, contracts, or DV01-to-quantity mapping.")
    if min_trade_size <= 0 or max_allowed_trade <= 0:
        raise ValueError("Trade size limits must be positive.")
    tickets: list[OrderTicket] = []
    all_instruments = sorted(set(target_positions) | set(current_positions))

    for instr in all_instruments:
        delta = target_positions.get(instr, 0.0) - current_positions.get(instr, 0.0)
        if abs(delta) < min_trade_size:
            continue

        qty = max(-max_allowed_trade, min(max_allowed_trade, delta))
        action = "BUY" if qty > 0 else "SELL"
        tickets.append(
            OrderTicket(
                instrument=instr,
                action=action,
                quantity=abs(qty),
                estimated_price=None,
                order_type="LMT",
                reason="Rebalance toward model target DV01",
                signal_date=signal_date,
                dry_run=dry_run,
            )
        )

    return tickets
