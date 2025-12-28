import requests


def get_price_binance():
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=5
        )
        return float(r.json()["price"])
    except:
        return None


def get_price_coinbase():
    try:
        r = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            timeout=5
        )
        return float(r.json()["data"]["amount"])
    except:
        return None


def get_price_coingecko():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=5
        )
        return float(r.json()["bitcoin"]["usd"])
    except:
        return None


def get_btc_price_usd():
    for fn in [get_price_binance, get_price_coinbase, get_price_coingecko]:
        price = fn()
        if price:
            return price
    return None