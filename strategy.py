import pandas as pd
import requests
from datetime import datetime, timedelta


# =========================================================
# SAFE DATA FETCHERS (FAULT-TOLERANT)
# =========================================================

def get_intraday_btc(minutes=300):
    """
    Get 1-minute BTCUSD prices (last ~5 hours)
    Returns pandas.Series or None
    """

    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"

    try:
        resp = requests.get(
            url,
            params=dict(
                vs_currency="usd",
                days=1,
                interval="minute"
            ),
            timeout=8
        )

        resp.raise_for_status()
        data = resp.json()

        # ---- SAFETY CHECKS ----
        if not isinstance(data, dict):
            return None

        if "prices" not in data:
            return None

        if not data["prices"]:
            return None

        prices = [row[1] for row in data["prices"] if len(row) >= 2]

        if len(prices) == 0:
            return None

        return pd.Series(prices).tail(minutes)

    except Exception as e:
        print("get_intraday_btc() FAILED:", e)
        return None



def get_htf_btc():
    """
    Get 1-hour BTC trend data (3 days)
    Used for higher-timeframe filter
    """

    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"

    try:
        resp = requests.get(
            url,
            params=dict(
                vs_currency="usd",
                days=3,
                interval="hourly"
            ),
            timeout=8
        )

        resp.raise_for_status()
        data = resp.json()

        if "prices" not in data or not data["prices"]:
            return None

        prices = [row[1] for row in data["prices"] if len(row) >= 2]

        if len(prices) == 0:
            return None

        return pd.Series(prices)

    except Exception as e:
        print("get_htf_btc() FAILED:", e)
        return None



# =========================================================
# INDICATORS
# =========================================================

def sma(s, n):
    return s.rolling(n).mean()


def rsi(s, n=14):
    d = s.diff()

    gain = d.clip(lower=0).ewm(alpha=1/n).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/n).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


def atr_like_vol(s, n=14):
    return s.diff().abs().rolling(n).mean()



# =========================================================
# NEWS + VOLATILITY EVENT FILTERS
# =========================================================

CRYPTO_PANIC_API_KEY = ""   # optional — leave blank if not available


def has_recent_news_risk(minutes=90):
    """
    Avoid trading during major news events
    If API unavailable → fail-safe returns False
    """

    if not CRYPTO_PANIC_API_KEY:
        return False

    try:
        r = requests.get(
            "https://cryptopanic.com/api/v1/posts/",
            params=dict(
                auth_token=CRYPTO_PANIC_API_KEY,
                currencies="BTC",
                filter="news"
            ),
            timeout=8
        ).json()

        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        for post in r.get("results", []):
            t = post.get("published_at", "").replace("Z", "+00:00")

            try:
                ts = datetime.fromisoformat(t)
            except:
                continue

            if ts < cutoff:
                continue

            text = (
                post.get("title", "") +
                post.get("description", "")
            ).lower()

            risk_terms = [
                "hack", "exploit", "ban", "lawsuit",
                "regulation", "liquidation",
                "exchange outage", "suspended", "shutdown"
            ]

            if any(w in text for w in risk_terms):
                return True

        return False

    except Exception:
        return False



def volatility_spike_detected(series, z_thresh=3.0):
    """
    Detect liquidation-style volatility spikes
    """
    try:
        returns = series.pct_change()
        z = (returns - returns.mean()) / returns.std()

        return z.tail(3).abs().max() > z_thresh
    except Exception:
        return False



# =========================================================
# HTF TREND FILTER
# =========================================================

def is_uptrend_htf():
    htf = get_htf_btc()

    if htf is None or len(htf) < 200:
        return None

    sma200 = sma(htf, 200)

    if sma200.isna().all():
        return None

    return htf.iloc[-1] > sma200.iloc[-1]



# =========================================================
# MAIN SIGNAL ENGINE
# =========================================================

def generate_signal():
    """
    Returns:
        ("LONG" | "SHORT" | "EXIT" | "HOLD", last_price)
    """

    data = get_intraday_btc()

    # ---- NO DATA = NO TRADE ----
    if data is None or len(data) < 120:
        return "HOLD", None

    price_prev = data.iloc[-2]
    price_now  = data.iloc[-1]

    # Core indicators
    sma_fast = sma(data, 20)
    sma_slow = sma(data, 50)

    sma_fast_prev = sma_fast.iloc[-2]
    sma_fast_now  = sma_fast.iloc[-1]

    sma_slow_prev = sma_slow.iloc[-2]
    sma_slow_now  = sma_slow.iloc[-1]

    r = rsi(data, 14)
    r_prev, r_now = r.iloc[-2], r.iloc[-1]

    vol = atr_like_vol(data, 14)
    low_vol = vol.iloc[-1] < vol.mean()



    # =====================================================
    # RISK BLOCKERS — news, spikes, chop
    # =====================================================

    if has_recent_news_risk(minutes=90):
        return "HOLD", price_now

    if volatility_spike_detected(data):
        return "HOLD", price_now

    if low_vol:
        return "HOLD", price_now



    # =====================================================
    # HIGHER-TIMEFRAME TREND FILTER
    # =====================================================

    htf_uptrend = is_uptrend_htf()

    # No trend info → don't trade
    if htf_uptrend is None:
        return "HOLD", price_now



    # =====================================================
    # LONG — pullback in uptrend
    # =====================================================

    if htf_uptrend:

        # RSI reversal entry
        if r_prev < 40 and r_now > 50:
            return "LONG", price_now

        # crossover fallback
        if sma_fast_prev < sma_slow_prev and sma_fast_now > sma_slow_now:
            return "LONG", price_now



    # =====================================================
    # SHORT — pullback in downtrend
    # =====================================================

    if not htf_uptrend:

        if r_prev > 60 and r_now < 50:
            return "SHORT", price_now

        if sma_fast_prev > sma_slow_prev and sma_fast_now < sma_slow_now:
            return "SHORT", price_now



    # =====================================================
    # EXIT — mean reversion
    # =====================================================

    if abs(price_now - sma_slow_now) < 0.1:
        return "EXIT", price_now


    return "HOLD", price_now