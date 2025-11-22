# app.py
import logging
from datetime import time as time_cls
from typing import Optional

import pandas as pd
import altair as alt
import streamlit as st

from config import load_config
from positions import Position
from strategy import strategy_step, heikin_ashi_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

st.set_page_config(page_title="NIFTY50 Heikin-Ashi Doji Algo", layout="wide")

st.title("📈 NIFTY50 Heikin-Ashi Doji Strategy (Upstox + Streamlit)")

st.markdown(
    """
**Disclaimer:** Educational template only.  
Use at your own risk. Test thoroughly in paper / sandbox before live trading.
"""
)

# -------- Session State Initialization --------
if "last_candle_ts" not in st.session_state:
    st.session_state.last_candle_ts = None

if "position" not in st.session_state:
    st.session_state.position: Optional[Position] = None

if "event_log" not in st.session_state:
    st.session_state.event_log = []

# -------- Sidebar Configuration --------
st.sidebar.header("Upstox API Settings")

client_id = st.sidebar.text_input("Client ID", value="")
client_secret = st.sidebar.text_input("Client Secret", value="", type="password")
redirect_uri = st.sidebar.text_input("Redirect URI", value="")
access_token = st.sidebar.text_input(
    "Access Token",
    value="",
    type="password",
    help="Access token from Upstox OAuth login (must be kept secret).",
)

st.sidebar.markdown("---")
instrument_key = st.sidebar.text_input(
    "Instrument Key",
    value="NSE_INDEX|Nifty 50",
    help="Set to actual NIFTY50 index key from Upstox master file.",
)

capital_per_trade = st.sidebar.number_input(
    "Capital per Trade (₹)",
    value=100000.0,
    min_value=1000.0,
    step=1000.0,
)

st.sidebar.markdown("### Risk Parameters")

profit_target_pct = st.sidebar.number_input(
    "Profit Target (%)", value=10.0, min_value=0.1, step=0.5
)
stop_loss_pct = st.sidebar.number_input(
    "Stop Loss (%)", value=1.0, min_value=0.1, step=0.1
)
trailing_stop_pct = st.sidebar.number_input(
    "Trailing Stop (%)", value=1.0, min_value=0.1, step=0.1
)

st.sidebar.markdown("### Trading Session")
session_start = st.sidebar.time_input("Session Start", value=time_cls(9, 15))
session_end = st.sidebar.time_input("Session End", value=time_cls(15, 15))

st.sidebar.markdown("---")
clear_log = st.sidebar.button("Clear Event Log")
if clear_log:
    st.session_state.event_log = []

# -------- Run Strategy Button --------
run_once = st.button("Run Strategy Step (Manual)")

# Build config from UI / env
config = load_config(
    client_id=client_id or None,
    client_secret=client_secret or None,
    redirect_uri=redirect_uri or None,
    access_token=access_token or None,
    instrument_key=instrument_key or None,
    capital_per_trade=capital_per_trade,
    profit_target_pct=profit_target_pct,
    stop_loss_pct=stop_loss_pct,
    trailing_stop_pct=trailing_stop_pct,
)

error_placeholder = st.empty()

if not config.access_token:
    error_placeholder.error("Access token is required. Please set it in the sidebar.")
else:
    if run_once:
        st.session_state.event_log.append("=== Running strategy step ===")
        last_ts, position = strategy_step(
            config=config,
            last_candle_ts=st.session_state.last_candle_ts,
            position=st.session_state.position,
            event_log=st.session_state.event_log,
            session_start=session_start,
            session_end=session_end,
        )
        st.session_state.last_candle_ts = last_ts
        st.session_state.position = position

# -------- Layout: left (position + log), right (chart) --------
left_col, right_col = st.columns([1, 1])

with left_col:
    st.subheader("Current Position")

    pos = st.session_state.position
    if pos is None:
        st.info("No open position.")
    else:
        colp1, colp2, colp3, colp4 = st.columns(4)
        colp1.metric("Side", pos.side)
        colp2.metric("Qty", pos.qty)
        colp3.metric("Entry Price", f"{pos.entry_price:.2f}")
        colp4.metric("Stop Loss", f"{pos.stop_loss:.2f}")

        colp5, colp6, colp7, _ = st.columns(4)
        colp5.metric("Target", f"{pos.target:.2f}")
        colp6.metric("Trailing Stop", f"{pos.trailing_stop:.2f}")
        colp7.metric("Extreme Price", f"{pos.extreme_price:.2f}")

    st.subheader("Event Log")
    if st.session_state.event_log:
        for line in reversed(st.session_state.event_log[-200:]):  # show last 200 entries
            st.text(line)
    else:
        st.write("No events yet.")

with right_col:
    st.subheader("Heikin-Ashi (Last N Candles)")

    if config.access_token:
        candles, ha = heikin_ashi_snapshot(config, limit=100)
        if ha:
            df_ha = pd.DataFrame(ha)
            # Ensure timestamp is datetime for charting
            df_ha["timestamp"] = pd.to_datetime(df_ha["timestamp"])

            # Build a candlestick-style chart for Heikin-Ashi
            base = alt.Chart(df_ha).encode(x="timestamp:T")

            rule = base.mark_rule().encode(
                y="ha_low:Q",
                y2="ha_high:Q",
            )

            bar = base.mark_bar().encode(
                y="ha_open:Q",
                y2="ha_close:Q",
            )

            chart = (rule + bar).properties(height=400)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No candle data available yet. Run at least one strategy step.")
    else:
        st.info("Provide a valid access token to load chart data.")
