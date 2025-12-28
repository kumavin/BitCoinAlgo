import json
from datetime import datetime
import pandas as pd
import os


EQUITY_FILE = "equity_curve.json"


def log_equity(value):
    row = {"time": datetime.now().isoformat(), "value": value}

    if os.path.exists(EQUITY_FILE):
        df = pd.read_json(EQUITY_FILE)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])

    df.to_json(EQUITY_FILE, orient="records")


def load_equity():
    if not os.path.exists(EQUITY_FILE):
        return None

    df = pd.read_json(EQUITY_FILE)
    df["time"] = pd.to_datetime(df["time"])
    return df