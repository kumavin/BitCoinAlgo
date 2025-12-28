import numpy as np
import pandas as pd


def compute_cagr(values, dates):
    if len(values) < 2:
        return 0.0

    duration_days = (dates.iloc[-1] - dates.iloc[0]).days

    if duration_days == 0:
        return 0.0

    years = duration_days / 365

    return (values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1


def compute_sharpe(values):
    returns = values.pct_change().dropna()
    return np.sqrt(252) * returns.mean() / returns.std()


def compute_drawdown(values):
    peak = values.cummax()
    return (values - peak) / peak