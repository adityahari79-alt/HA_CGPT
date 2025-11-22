# upstox_wrappers.py
import logging
from typing import Any, Dict, List, Optional

import requests
import upstox_client
from upstox_client.rest import ApiException

from config import Config

log = logging.getLogger(__name__)


def exchange_auth_code_for_token(config: Config, code: str) -> Dict[str, Any]:
    """
    Helper to exchange manual login 'code' for an access_token.
    """
    url = f"{config.base_url_v2}/login/authorization/token"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "code": code,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post(url, headers=headers, data=data)
    resp.raise_for_status()
    return resp.json()


class UpstoxRestOHLCClient:
    """
    Lightweight REST client for intraday OHLC candles via HTTP GET.
    """

    def __init__(self, config: Config):
        self.config = config

    def get_intraday_candles(self) -> List[Dict[str, Any]]:
        """
        Returns candles as:
        [ { 'timestamp': ts, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v }, ... ]
        """
        url = f"{self.config.base_url_v2}/historical-candle/intraday/{self.config.instrument_key}/{self.config.interval}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.access_token}",
        }
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            log.error("Intraday candle API error: %s - %s", resp.status_code, resp.text)
            return []

        data = resp.json()
        raw_candles = []
        if isinstance(data.get("data"), dict):
            raw_candles = data["data"].get("candles", []) or []

        candles = []
        for row in raw_candles:
            ts, o, h, l, c, v = row
            candles.append(
                {
                    "timestamp": ts,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                }
            )
        return candles


class UpstoxTradingClient:
    """
    Wrapper around Upstox Python SDK for:
    - placing orders
    - getting LTP
    """

    def __init__(self, config: Config):
        self.config = config
        configuration = upstox_client.Configuration()
        configuration.access_token = config.access_token
        self.api_client = upstox_client.ApiClient(configuration)

        self.order_api = upstox_client.OrderApi(self.api_client)
        self.quote_api = upstox_client.MarketQuoteApi(self.api_client)

        self.api_version = "2.0"

    def get_ltp(self) -> Optional[float]:
        try:
            symbols = self.config.instrument_key
            res = self.quote_api.ltp(symbols, self.api_version)
            ltp_data = res.data.get(self.config.instrument_key)
            if not ltp_data:
                return None
            return float(ltp_data.get("ltp"))
        except ApiException as e:
            log.error("Error getting LTP: %s", e)
            return None

    def place_market_order(self, side: str, qty: int, tag: str = "nifty50_heikin_doji_algo") -> Optional[str]:
        """
        side: 'BUY' or 'SELL'
        Returns order_id or None.
        """
        body = upstox_client.PlaceOrderRequest(
            quantity=qty,
            product=self.config.product,
            validity="DAY",
            price=0.0,
            tag=tag,
            instrument_token=self.config.instrument_key,
            order_type="MARKET",
            transaction_type=side,
            disclosed_quantity=0,
            trigger_price=0.0,
            is_amo=False,
        )
        try:
            resp = self.order_api.place_order(body, self.api_version)
            order_id = resp.data.get("order_id")
            log.info("Placed %s order: %s (qty=%s)", side, order_id, qty)
            return order_id
        except ApiException as e:
            log.error("Error placing %s order: %s", side, e)
            return None
