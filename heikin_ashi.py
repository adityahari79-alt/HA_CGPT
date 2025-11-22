# heikin_ashi.py
from typing import Dict, List, Optional


def compute_heikin_ashi(candles: List[Dict]) -> List[Dict]:
    """
    Convert OHLC to Heikin Ashi candles.
    """
    ha = []
    prev_ha_open = None
    prev_ha_close = None

    for c in candles:
        o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
        ha_close = (o + h + l + cl) / 4.0

        if prev_ha_open is None:
            ha_open = (o + cl) / 2.0
        else:
            ha_open = (prev_ha_open + prev_ha_close) / 2.0

        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)

        candle_ha = {
            "timestamp": c["timestamp"],
            "ha_open": ha_open,
            "ha_high": ha_high,
            "ha_low": ha_low,
            "ha_close": ha_close,
            "volume": c["volume"],
        }
        ha.append(candle_ha)
        prev_ha_open, prev_ha_close = ha_open, ha_close

    return ha


def classify_heikin_ashi_doji(
    ha_open: float,
    ha_high: float,
    ha_low: float,
    ha_close: float,
    max_body_pct: float = 0.1,
    min_shadow_pct: float = 0.3,
) -> Optional[Dict]:
    """
    Advanced Doji classification on Heikin Ashi.
    Types: standard, dragonfly, gravestone, long_legged.
    """
    rang = ha_high - ha_low
    if rang <= 0:
        return None

    body = abs(ha_close - ha_open)
    body_pct = body / rang

    if body_pct > max_body_pct:
        return None

    upper_shadow = ha_high - max(ha_open, ha_close)
    lower_shadow = min(ha_open, ha_close) - ha_low
    upper_pct = upper_shadow / rang
    lower_pct = lower_shadow / rang

    doji_type = "standard"
    if upper_pct < 0.1 and lower_pct > 0.6:
        doji_type = "dragonfly"
    elif lower_pct < 0.1 and upper_pct > 0.6:
        doji_type = "gravestone"
    elif upper_pct > min_shadow_pct and lower_pct > min_shadow_pct:
        doji_type = "long_legged"

    return {
        "type": doji_type,
        "body_pct": body_pct,
        "upper_pct": upper_pct,
        "lower_pct": lower_pct,
    }
