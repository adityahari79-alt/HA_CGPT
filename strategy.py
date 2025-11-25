# strategy.py
import logging
from datetime import datetime, time as time_cls
from typing import Any, Dict, List, Optional, Tuple

import pytz

from config import Config
from conditions import ConditionEngine, HeikinAshiDojiReversalCondition
from heikin_ashi import compute_heikin_ashi
from notifications import ConsoleNotifier, ListNotifier, WebhookNotifier
from positions import Position, PositionManager
from upstox_wrappers import UpstoxRestOHLCClient, UpstoxTradingClient

log = logging.getLogger(__name__)


def _get_now_time(timezone_name: Optional[str]) -> time_cls:
    """
    Returns current local time in the given timezone.
    If timezone is invalid or None, falls back to server local time.
    """
    try:
        if timezone_name:
            tz = pytz.timezone(timezone_name)
            return datetime.now(tz).time()
    except Exception:
        # Fallback to server local time
        pass
    return datetime.now().astimezone().time()


def strategy_step(
    config: Config,
    last_candle_ts: Optional[str],
    position: Optional[Position],
    event_log: Optional[List[str]] = None,
    session_start: Optional[time_cls] = None,
    session_end: Optional[time_cls] = None,
    respect_trading_hours: bool = True,
    timezone_name: Optional[str] = "Asia/Kolkata",
) -> Tuple[Optional[str], Optional[Position]]:
    """
    One iteration of the strategy:
    - optionally respect trading session time window (with timezone)
    - fetch intraday candles
    - compute Heikin Ashi
    - detect Doji reversal (long/short)
    - manage trailing SL / TP / SL

    Returns updated (last_candle_ts, position).
    """
    if event_log is None:
        event_log = []

    # Trading session filter
    if respect_trading_hours and session_start and session_end and session_start < session_end:
        now_time = _get_now_time(timezone_name)
        if not (session_start <= now_time <= session_end):
            event_log.append(
                f"Outside trading window ({session_start.strftime('%H:%M')}–"
                f"{session_end.strftime('%H:%M')}) in {timezone_name or 'server timezone'}, "
                f"current time: {now_time.strftime('%H:%M:%S')}. Skipping trading step."
            )
            return last_candle_ts, position

    ohlc_client = UpstoxRestOHLCClient(config)
    trade_client = UpstoxTradingClient(config)

    notifiers = [ConsoleNotifier(), ListNotifier(event_log)]
    if config.webhook_url:
        notifiers.append(WebhookNotifier(config.webhook_url))

    cond_engine = ConditionEngine(
        conditions=[HeikinAshiDojiReversalCondition(require_trend=True)],
        notifiers=notifiers,
    )

    pos_mgr = PositionManager(config, trade_client, notifiers)
    pos_mgr.position = position

    candles = ohlc_client.get_intraday_candles()
    if not candles:
        event_log.append("No candles returned from Upstox.")
        return last_candle_ts, pos_mgr.position

    latest = candles[-1]
    new_last_ts = last_candle_ts

    if latest["timestamp"] != last_candle_ts:
        new_last_ts = latest["timestamp"]

        ha = compute_heikin_ashi(candles)
        context: Dict[str, Any] = {"candles": candles, "heikin_ashi": ha}

        cond = cond_engine.evaluate(context)

        if cond and not pos_mgr.has_open_position():
            last_ha = ha[-1]
            entry_price = last_ha["ha_close"]
            direction = context.get("signal_direction")
            if direction == "LONG":
                pos_mgr.open_long(entry_price)
            elif direction == "SHORT":
                pos_mgr.open_short(entry_price)

    # Update trailing SL / TP / SL on current LTP
    ltp = trade_client.get_ltp()
    if ltp is not None:
        pos_mgr.on_price_update(ltp)
        event_log.append(f"LTP: {ltp:.2f}")
    else:
        event_log.append("Unable to fetch LTP.")

    return new_last_ts, pos_mgr.position


def heikin_ashi_snapshot(
    config: Config,
    limit: int = 100,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetch latest intraday candles and return both:
    - raw OHLC candles
    - Heikin-Ashi candles

    Limited to last `limit` candles for charting.
    """
    ohlc_client = UpstoxRestOHLCClient(config)
    candles = ohlc_client.get_intraday_candles()
    if not candles:
        return [], []

    ha = compute_heikin_ashi(candles)

    if limit and len(candles) > limit:
        candles = candles[-limit:]
    if limit and len(ha) > limit:
        ha = ha[-limit:]

    return candles, ha
