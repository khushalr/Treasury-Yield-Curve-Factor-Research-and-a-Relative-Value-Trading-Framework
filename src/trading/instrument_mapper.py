"""Mapping from abstract tenor DV01s into tradable instrument intents."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProposedInstrumentTrade:
    instrument: str
    tenor: int
    target_exposure: float
    mode: str
    metadata: dict[str, str]


def map_instruments(
    exposures: dict[int, float],
    mode: str,
    etf_proxy_map: dict[int, str] | None = None,
) -> list[ProposedInstrumentTrade]:
    """Map abstract exposures into instrument tickets.

    Fully implemented: paper_synthetic, etf_proxy.
    Stubbed: futures_proxy, cash_treasury.
    """

    etf_proxy_map = etf_proxy_map or {}
    tickets: list[ProposedInstrumentTrade] = []

    if mode == "paper_synthetic":
        for tenor, exp in exposures.items():
            tickets.append(
                ProposedInstrumentTrade(
                    instrument=f"SYNTH_{tenor}Y",
                    tenor=tenor,
                    target_exposure=exp,
                    mode=mode,
                    metadata={"tradable": "false", "description": "Synthetic paper-only exposure"},
                )
            )
        return tickets

    if mode == "etf_proxy":
        for tenor, exp in exposures.items():
            symbol = etf_proxy_map.get(tenor, f"ETF_TENOR_{tenor}")
            tickets.append(
                ProposedInstrumentTrade(
                    instrument=symbol,
                    tenor=tenor,
                    target_exposure=exp,
                    mode=mode,
                    metadata={"tradable": "paper_only", "mapping": "proxy"},
                )
            )
        return tickets

    if mode == "futures_proxy":
        raise NotImplementedError("futures_proxy is a planned extension; add contract-roll and DV01 mapping first.")

    if mode == "cash_treasury":
        raise NotImplementedError("cash_treasury is a planned extension; add CUSIP universe and bond-level risk model first.")

    raise ValueError(f"Unsupported mode: {mode}")
