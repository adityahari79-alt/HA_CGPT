# positions.py
import logging
import math
from dataclasses import dataclass
from typing import List, Optional

from config import Config
from notifications import Notifier
from upstox_wrappers import UpstoxTradingClient

log = logging.getLogger(__name__)


@dataclass
class Position:
    side: str           # "LONG" or "SHORT"
    qty: int
    entry_price: float
    stop_loss: float
    target: float
    trailing_stop: float
    extreme_price: float
    order_id: Optional[str] = None


class PositionManager:
    """
    Handles 1% SL, 10% target, 1% trailing stop
    for both LONG and SHORT.
    """

    def __init__(self, config: Config, client: UpstoxTradingClient, notifiers: List[Notifier]):
        self.config = config
        self.client = client
        self.notifiers = notifiers
        self.position: Optional[Position] = None

    def has_open_position(self) -> bool:
        return self.position is not None

    def _notify(self, msg: str) -> None:
        for n in self.notifiers:
            n.notify(msg)

    def _calc_qty_from_risk(self, entry_price: float) -> int:
        risk_amount = self.config.capital_per_trade * (self.config.max_risk_per_trade_pct / 100.0)
        per_unit_risk = entry_price * (self.config.stop_loss_pct / 100.0)
        if per_unit_risk <= 0:
            return self.config.fallback_qty
        qty = int(math.floor(risk_amount / per_unit_risk))
        return max(qty, self.config.fallback_qty)

    def _open_position(self, side: str, entry_price: float) -> None:
        if self.position is not None:
            log.info("Position already open, skipping entry.")
            return

        qty = self._calc_qty_from_risk(entry_price)

        if side == "LONG":
            stop_loss = entry_price * (1.0 - self.config.stop_loss_pct / 100.0)
            target = entry_price * (1.0 + self.config.profit_target_pct / 100.0)
            trailing_stop = stop_loss
            extreme_price = entry_price
            order_side = "BUY"
        else:  # SHORT
            stop_loss = entry_price * (1.0 + self.config.stop_loss_pct / 100.0)
            target = entry_price * (1.0 - self.config.profit_target_pct / 100.0)
            trailing_stop = stop_loss
            extreme_price = entry_price
            order_side = "SELL"

        order_id = self.client.place_market_order(order_side, qty)
        if not order_id:
            self._notify(f"{side} entry order failed, not opening position.")
            return

        self.position = Position(
            side=side,
            qty=qty,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            trailing_stop=trailing_stop,
            extreme_price=extreme_price,
            order_id=order_id,
        )

        self._notify(
            f"Opened {side} position (qty={qty}) at {entry_price:.2f}, "
            f"SL={stop_loss:.2f} ({self.config.stop_loss_pct:.1f}%), "
            f"TP={target:.2f} ({self.config.profit_target_pct:.1f}%), "
            f"trail={self.config.trailing_stop_pct:.1f}%."
        )

    def open_long(self, entry_price: float) -> None:
        self._open_position("LONG", entry_price)

    def open_short(self, entry_price: float) -> None:
        self._open_position("SHORT", entry_price)

    def _close_position(self, reason: str, exit_price: float) -> None:
        if not self.position:
            return

        pos = self.position
        if pos.side == "LONG":
            order_side = "SELL"
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100.0
        else:
            order_side = "BUY"
            pnl_pct = (pos.entry_price - exit_price) / pos.entry_price * 100.0

        order_id = self.client.place_market_order(order_side, pos.qty)
        if order_id:
            self._notify(
                f"Closed {pos.side} (reason: {reason}) at {exit_price:.2f}, "
                f"entry={pos.entry_price:.2f}, P&L={pnl_pct:.2f}%."
            )
        else:
            self._notify(f"Failed to place exit order (reason: {reason}).")

        self.position = None

    def on_price_update(self, price: float) -> None:
        if not self.position:
            return

        pos = self.position

        if pos.side == "LONG":
            # update extreme and trail
            if price > pos.extreme_price:
                pos.extreme_price = price
                new_trail = pos.extreme_price * (1.0 - self.config.trailing_stop_pct / 100.0)
                if new_trail > pos.trailing_stop:
                    pos.trailing_stop = new_trail

            if price >= pos.target:
                self._close_position("profit_target_hit", price)
                return

            if price <= pos.stop_loss:
                self._close_position("hard_stop_loss_hit", price)
                return

            if price <= pos.trailing_stop:
                self._close_position("trailing_stop_hit", price)
                return

        else:  # SHORT
            if price < pos.extreme_price:
                pos.extreme_price = price
                new_trail = pos.extreme_price * (1.0 + self.config.trailing_stop_pct / 100.0)
                if new_trail < pos.trailing_stop:
                    pos.trailing_stop = new_trail

            if price <= pos.target:
                self._close_position("profit_target_hit", price)
                return

            if price >= pos.stop_loss:
                self._close_position("hard_stop_loss_hit", price)
                return

            if price >= pos.trailing_stop:
                self._close_position("trailing_stop_hit", price)
                return
