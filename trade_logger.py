import json
from datetime import datetime


LOG_FILE = "trades.jsonl"


def log_trade(side, price, qty, pnl=0):
    record = {
        "time": datetime.now().isoformat(),
        "side": side,
        "price": price,
        "qty": qty,
        "pnl": pnl
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_trades():
    trades = []
    try:
        with open(LOG_FILE) as f:
            for line in f:
                trades.append(json.loads(line))
    except FileNotFoundError:
        pass

    return trades