"""Configuration defaults for the daily PCA fly signal pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ENTRY_Z = 2.5
SIGNAL_CAP = 3.0
TARGET_DAILY_VOL = 0.01
ROLLING_PCA_WINDOW = 504
SELECTED_TENORS = [5, 7, 10]

MODE = "paper_synthetic"

ALLOW_TRADING = False
PAPER_TRADING = True
LIVE_TRADING = False
DRY_RUN = True

IBKR_HOST = "127.0.0.1"
IBKR_PORT = 7497
IBKR_CLIENT_ID = 7

MAX_GROSS_DV01 = 500.0
MAX_LEG_DV01 = 250.0
MAX_DAILY_LOSS = 200.0
MAX_POSITION_CHANGE = 250.0
MAX_BID_ASK_BPS = 2.0

DATA_PATH = Path("feds200628.csv")
REPORTS_DIR = Path("reports")
STALE_DATA_MAX_DAYS = 5
ROLLING_SIGNAL_WINDOW = 126
MIN_TRADE_SIZE = 1.0
ETF_PROXY_MAP = {5: "IEF", 7: "IEF", 10: "TLT"}


@dataclass(slots=True)
class PipelineConfig:
    """Runtime configuration container for scripts and modules."""

    entry_z: float = ENTRY_Z
    signal_cap: float = SIGNAL_CAP
    target_daily_vol: float = TARGET_DAILY_VOL
    rolling_pca_window: int = ROLLING_PCA_WINDOW
    rolling_signal_window: int = ROLLING_SIGNAL_WINDOW
    selected_tenors: list[int] = field(default_factory=lambda: list(SELECTED_TENORS))
    mode: str = MODE
    allow_trading: bool = ALLOW_TRADING
    paper_trading: bool = PAPER_TRADING
    live_trading: bool = LIVE_TRADING
    dry_run: bool = DRY_RUN
    ibkr_host: str = IBKR_HOST
    ibkr_port: int = IBKR_PORT
    ibkr_client_id: int = IBKR_CLIENT_ID
    max_gross_dv01: float = MAX_GROSS_DV01
    max_leg_dv01: float = MAX_LEG_DV01
    max_daily_loss: float = MAX_DAILY_LOSS
    max_position_change: float = MAX_POSITION_CHANGE
    max_bid_ask_bps: float = MAX_BID_ASK_BPS
    stale_data_max_days: int = STALE_DATA_MAX_DAYS
    min_trade_size: float = MIN_TRADE_SIZE
    data_path: Path = DATA_PATH
    reports_dir: Path = REPORTS_DIR
    etf_proxy_map: dict[int, str] = field(default_factory=lambda: dict(ETF_PROXY_MAP))
