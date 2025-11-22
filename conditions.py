# conditions.py
from typing import Any, Dict, List, Optional

from heikin_ashi import classify_heikin_ashi_doji
from notifications import Notifier


class Condition:
    name: str = "base_condition"

    def check(self, context: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def format_message(self, context: Dict[str, Any]) -> str:
        return self.name


class HeikinAshiDojiReversalCondition(Condition):
    """
    Detects a Heikin Ashi Doji on latest candle and infers reversal direction.
    prev bullish → SHORT
    prev bearish → LONG
    """
    name = "heikin_ashi_doji_reversal"

    def __init__(self, require_trend: bool = True):
        self.require_trend = require_trend

    def check(self, context: Dict[str, Any]) -> bool:
        ha = context.get("heikin_ashi", [])
        if len(ha) < 2:
            return False

        prev_candle = ha[-2]
        last_candle = ha[-1]

        doji_info = classify_heikin_ashi_doji(
            last_candle["ha_open"],
            last_candle["ha_high"],
            last_candle["ha_low"],
            last_candle["ha_close"],
        )
        if not doji_info:
            return False

        context["doji_info"] = doji_info

        prev_body = prev_candle["ha_close"] - prev_candle["ha_open"]
        trend_dir = "bullish" if prev_body > 0 else "bearish"
        context["prev_trend_dir"] = trend_dir

        # optional: require strong previous body
        if self.require_trend:
            prev_range = prev_candle["ha_high"] - prev_candle["ha_low"]
            if prev_range <= 0:
                return False
            prev_body_abs = abs(prev_body)
            prev_body_pct = prev_body_abs / prev_range
            if prev_body_pct <= 0.3:
                return False

        if prev_body > 0:
            context["signal_direction"] = "SHORT"
        else:
            context["signal_direction"] = "LONG"

        return True

    def format_message(self, context: Dict[str, Any]) -> str:
        doji = context.get("doji_info", {})
        direction = context.get("signal_direction", "UNKNOWN")
        ts = context["heikin_ashi"][-1]["timestamp"]
        return (
            f"Heikin Ashi Doji ({doji.get('type', 'unknown')}) on {ts}, "
            f"prev_trend={context.get('prev_trend_dir')}, signal={direction}"
        )


class ConditionEngine:
    def __init__(self, conditions: List[Condition], notifiers: List[Notifier]):
        self.conditions = conditions
        self.notifiers = notifiers

    def evaluate(self, context: Dict[str, Any]) -> Optional[Condition]:
        for cond in self.conditions:
            if cond.check(context):
                msg = cond.format_message(context)
                for n in self.notifiers:
                    n.notify(msg)
                return cond
        return None
