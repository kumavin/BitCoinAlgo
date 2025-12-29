import streamlit as st
import pandas as pd
import time

from trader import BTCTrader
from prices import get_btc_price_usd
from state_manager import save_state, load_state
from trade_logger import log_trade, load_trades
from equity_logger import log_equity, load_equity
from performance import compute_cagr, compute_sharpe, compute_drawdown

from strategy import generate_signal
from streamlit_autorefresh import st_autorefresh


st.set_page_config(layout="wide")
st.title("₿ Bitcoin Trading Cockpit — USD (Paper Trading Bot)")


# =========================================================
# AUTO REFRESH
# =========================================================
st.sidebar.subheader("⏱ Auto Refresh")

REFRESH_MS = 5000

auto_refresh = st.sidebar.toggle(
    "Enable Auto Refresh (5s)",
    value=True
)

if auto_refresh:
    st_autorefresh(interval=REFRESH_MS, key="auto_cycle")

st.caption(f"🔄 Last refreshed {time.strftime('%H:%M:%S')}")


# =========================================================
# LOAD TRADER STATE
# =========================================================
if "trader" not in st.session_state:
    st.session_state.trader = BTCTrader()
    load_state(st.session_state.trader)

trader = st.session_state.trader


# =========================================================
# SAFE STATE MIGRATION
# =========================================================
if trader.position and isinstance(trader.position, dict):

    trader.position.setdefault("side", "LONG")
    trader.position.setdefault("qty", 0)
    trader.position.setdefault("entry", 0)

    trader.position.setdefault("trail_pct", 0.03)
    trader.position.setdefault("tp_pct", 0.08)

    entry = trader.position["entry"]

    if trader.position["side"] == "LONG":
        trader.position.setdefault("high", entry)
        trader.position.setdefault(
            "trail_level",
            entry * (1 - trader.position["trail_pct"])
        )
        trader.position.setdefault(
            "tp_level",
            entry * (1 + trader.position["tp_pct"])
        )

    elif trader.position["side"] == "SHORT":
        trader.position.setdefault("low", entry)
        trader.position.setdefault(
            "trail_level",
            entry * (1 + trader.position["trail_pct"])
        )
        trader.position.setdefault(
            "tp_level",
            entry * (1 - trader.position["tp_pct"])
        )


# =========================================================
# FETCH BTC PRICE
# =========================================================
price = get_btc_price_usd()

if not price:
    st.error("❌ Unable to fetch BTC price — trading paused")
    price = 0

st.metric("Bitcoin Price (USD)", round(price, 2) if price else "N/A")


# =========================================================
# RISK SETTINGS
# =========================================================
st.sidebar.subheader("⚙ Risk Controls")

trail_pct = st.sidebar.number_input(
    "Trailing Stop %", min_value=0.5, max_value=20.0, value=3.0
) / 100

tp_pct = st.sidebar.number_input(
    "Take Profit %", min_value=1.0, max_value=50.0, value=8.0
) / 100


def apply_trailing_levels(side, entry_price):

    trader.position["trail_pct"] = trail_pct
    trader.position["tp_pct"] = tp_pct

    if side == "LONG":
        trader.position["high"] = entry_price
        trader.position["trail_level"] = entry_price * (1 - trail_pct)
        trader.position["tp_level"] = entry_price * (1 + tp_pct)

    elif side == "SHORT":
        trader.position["low"] = entry_price
        trader.position["trail_level"] = entry_price * (1 + trail_pct)
        trader.position["tp_level"] = entry_price * (1 - tp_pct)


# =========================================================
# DUPLICATE TRADE PROTECTION
# =========================================================
def same_trade_already_open(signal):
    """
    Prevent duplicate trades:
    - LONG when already LONG
    - SHORT when already SHORT
    """
    if not trader.position:
        return False

    side = trader.position["side"]

    return (
        (signal == "LONG" and side == "LONG") or
        (signal == "SHORT" and side == "SHORT")
    )


# =========================================================
# AUTO TRADING STRATEGY
# =========================================================
st.sidebar.subheader("🤖 Strategy Automation")

auto_trading = st.sidebar.toggle(
    "Enable Auto Trading",
    value=True  # enabled by default
)

position_size = st.sidebar.number_input(
    "Position Size (BTC)",
    min_value=0.001,
    max_value=5.0,
    value=0.01,
    step=0.001
)


if auto_trading:

    signal, sig_price = generate_signal()

    if sig_price is None:
        st.info("🤖 Strategy HOLD — waiting for valid data")
        signal = "HOLD"

    st.sidebar.write(f"Strategy Signal: **{signal}**")

    # =====================================================
    # IGNORE SAME-SIDE SIGNALS
    # =====================================================
    if same_trade_already_open(signal):
        st.sidebar.write("⏸ Position already open — no action taken")
        signal = "HOLD"

    # =====================================================
    # EXECUTE STATE-CHANGE ACTIONS ONLY
    # =====================================================

    # ---------- ENTER LONG ----------
    if signal == "LONG" and price:

        trader.close_position(price)  # closes short if any
        trader.open_long(price, position_size)

        apply_trailing_levels("LONG", price)
        save_state(trader)

        log_trade("AUTO_LONG", price, position_size, 0)

        st.success("🤖 Auto-Trade: LONG opened")


    # ---------- ENTER SHORT ----------
    elif signal == "SHORT" and price:

        trader.close_position(price)
        trader.open_short(price, position_size)

        apply_trailing_levels("SHORT", price)
        save_state(trader)

        log_trade("AUTO_SHORT", price, position_size, 0)

        st.error("🤖 Auto-Trade: SHORT opened")


    # ---------- EXIT ----------
    elif signal == "EXIT" and trader.position and price:

        pnl = trader.close_position(price)
        save_state(trader)

        log_trade("AUTO_EXIT", price, 0, pnl)

        st.warning(f"🤖 Auto-Exit — PnL ${round(pnl,2)}")


# =========================================================
# AUTO TRAILING STOP / TAKE PROFIT
# =========================================================
if trader.position and price:

    side = trader.position["side"]
    entry = trader.position["entry"]
    qty = trader.position["qty"]

    # ----- LONG -----
    if side == "LONG":

        if price > trader.position.get("high", entry):
            trader.position["high"] = price
            trader.position["trail_level"] = price * (1 - trader.position["trail_pct"])

        if price <= trader.position["trail_level"]:
            pnl = trader.close_position(price)
            log_trade("TRAIL_STOP_EXIT", price, 0, pnl)
            save_state(trader)
            st.error(f"🔻 Trailing Stop Hit — PnL ${round(pnl,2)}")

        elif price >= trader.position["tp_level"]:
            pnl = trader.close_position(price)
            log_trade("TAKE_PROFIT_EXIT", price, 0, pnl)
            save_state(trader)
            st.success(f"🎯 Take Profit Hit — PnL ${round(pnl,2)}")

    # ----- SHORT -----
    elif side == "SHORT":

        if price < trader.position.get("low", entry):
            trader.position["low"] = price
            trader.position["trail_level"] = price * (1 + trader.position["trail_pct"])

        if price >= trader.position["trail_level"]:
            pnl = trader.close_position(price)
            log_trade("TRAIL_STOP_EXIT", price, 0, pnl)
            save_state(trader)
            st.error(f"🔻 Trailing Stop Hit — PnL ${round(pnl,2)}")

        elif price <= trader.position["tp_level"]:
            pnl = trader.close_position(price)
            log_trade("TAKE_PROFIT_EXIT", price, 0, pnl)
            save_state(trader)
            st.success(f"🎯 Take Profit Hit — PnL ${round(pnl,2)}")


# =========================================================
# OPEN POSITION — LIVE PNL
# =========================================================
st.subheader("📈 Open Position — Live PnL")

if trader.position and price:

    side = trader.position["side"]
    entry = trader.position["entry"]
    qty = trader.position["qty"]

    pnl = (price - entry) * qty if side == "LONG" else (entry - price) * qty

    row = {
        "Side": side,
        "Entry $": round(entry, 2),
        "Qty (BTC)": qty,
        "Live $": round(price, 2),
        "PnL $": round(pnl, 2),
        "Trail Stop $": round(trader.position["trail_level"], 2),
        "Take Profit $": round(trader.position["tp_level"], 2),
        "Since": trader.position["time"]
    }

    st.dataframe(pd.DataFrame([row]))
    st.metric("Total Live PnL $", round(pnl, 2))

else:
    st.info("No active position")


# =========================================================
# MANUAL TRADING CONSOLE
# =========================================================
st.subheader("⚡ Manual Trading Console")

col1, col2, col3 = st.columns(3)

with col1:
    qty = st.number_input(
        "Trade Size (BTC)",
        min_value=0.001,
        max_value=5.0,
        value=0.01,
        step=0.001
    )

with col2:
    if st.button("🚀 Open LONG") and price:
        trader.close_position(price)
        trader.open_long(price, qty)
        apply_trailing_levels("LONG", price)
        save_state(trader)
        log_trade("MANUAL_LONG", price, qty, 0)
        st.success("Opened LONG")

with col3:
    if st.button("🔻 Open SHORT") and price:
        trader.close_position(price)
        trader.open_short(price, qty)
        apply_trailing_levels("SHORT", price)
        save_state(trader)
        log_trade("MANUAL_SHORT", price, qty, 0)
        st.error("Opened SHORT")


if st.button("❌ Exit Position") and trader.position and price:
    pnl = trader.close_position(price)
    save_state(trader)
    log_trade("MANUAL_EXIT", price, 0, pnl)
    st.warning(f"Position closed — PnL ${round(pnl,2)}")


# =========================================================
# PORTFOLIO SUMMARY
# =========================================================
portfolio_value = trader.value(price) if price else trader.cash

st.subheader("💰 Portfolio Summary")

c1, c2 = st.columns(2)
c1.metric("Portfolio Value $", round(portfolio_value, 2))
c2.metric("Available Cash $", round(trader.cash, 2))

log_equity(portfolio_value)


# =========================================================
# ANALYTICS
# =========================================================
tabs = st.tabs(["📒 Trades", "📈 Equity", "⚠️ Drawdown"])

with tabs[0]:
    trades = load_trades()
    if trades and len(trades) > 0:
        st.subheader("📒 Trade History")
        st.dataframe(pd.DataFrame(trades))
    else:
        st.info("No trades yet")

with tabs[1]:
    df = load_equity()
    if df is not None:
        st.line_chart(df.set_index("time")["value"])
        cagr = compute_cagr(df["value"], df["time"])
        sharpe = compute_sharpe(df["value"])
        c1, c2 = st.columns(2)
        c1.metric("CAGR %", round(cagr * 100, 2))
        c2.metric("Sharpe Ratio", round(sharpe, 2))
    else:
        st.info("Equity curve will appear after logs accumulate")

with tabs[2]:
    if df is not None:
        dd = compute_drawdown(df["value"])
        st.line_chart(pd.DataFrame({"Drawdown": dd}, index=df["time"]))
    else:
        st.info("No drawdown data yet")
