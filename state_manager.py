import json
import os


STATE_FILE = "btc_state.json"


def save_state(trader):
    with open(STATE_FILE, "w") as f:
        json.dump({
            "cash": trader.cash,
            "position": trader.position
        }, f)


def load_state(trader):
    if not os.path.exists(STATE_FILE):
            return

    with open(STATE_FILE) as f:
        data = json.load(f)
        trader.cash = data["cash"]
        trader.position = data["position"]