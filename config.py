# config.py
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    # Upstox OAuth app config
    client_id: str
    client_secret: str
    redirect_uri: str

    # Daily access token
    access_token: str

    # Trading config (NIFTY50, 5 min, long+short)
    instrument_key: str = "NSE_INDEX|Nifty 50"  # CHANGE to actual Upstox key
    interval: str = "5minute"

    product: str = "I"           # intraday
    fallback_qty: int = 50       # fallback quantity / lot

    # Risk management
    capital_per_trade: float = 100000.0
    max_risk_per_trade_pct: float = 1.0
    profit_target_pct: float = 10.0
    stop_loss_pct: float = 1.0
    trailing_stop_pct: float = 1.0

    # Polling (not really used in Streamlit, we run step-by-step)
    poll_interval_seconds: int = 10

    # Alerts
    webhook_url: Optional[str] = None

    # Upstox API base
    base_url_v2: str = "https://api.upstox.com/v2"


def load_config(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    access_token: Optional[str] = None,
    instrument_key: Optional[str] = None,
    capital_per_trade: Optional[float] = None,
    profit_target_pct: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
    trailing_stop_pct: Optional[float] = None,
) -> Config:
    """
    Loads config from environment variables, but allows overriding
    via function arguments (used by Streamlit UI).
    """
    cfg = Config(
        client_id=client_id or os.getenv("UPSTOX_CLIENT_ID", ""),
        client_secret=client_secret or os.getenv("UPSTOX_CLIENT_SECRET", ""),
        redirect_uri=redirect_uri or os.getenv("UPSTOX_REDIRECT_URI", ""),
        access_token=access_token or os.getenv("UPSTOX_ACCESS_TOKEN", ""),
    )

    if instrument_key:
        cfg.instrument_key = instrument_key

    if capital_per_trade is not None:
        cfg.capital_per_trade = capital_per_trade

    if profit_target_pct is not None:
        cfg.profit_target_pct = profit_target_pct

    if stop_loss_pct is not None:
        cfg.stop_loss_pct = stop_loss_pct

    if trailing_stop_pct is not None:
        cfg.trailing_stop_pct = trailing_stop_pct

    # Optional webhook URL from env
    cfg.webhook_url = os.getenv("UPSTOX_WEBHOOK_URL") or None

    return cfg
