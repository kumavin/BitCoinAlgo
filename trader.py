from datetime import datetime


class BTCTrader:

    def __init__(self, starting_cash=100000):
        self.cash = starting_cash
        self.position = None   # None | LONG | SHORT


    def open_long(self, price, qty):
        cost = price * qty
        if cost > self.cash:
            return False

        self.cash -= cost

        self.position = {
            "side": "LONG",
            "entry": price,
            "qty": qty,
            "high": price,
            "time": datetime.now().isoformat()
        }
        return True


    def open_short(self, price, qty):
        # simulated borrow
        self.position = {
            "side": "SHORT",
            "entry": price,
            "qty": qty,
            "low": price,
            "time": datetime.now().isoformat()
        }
        return True


    def close_position(self, price):
        if not self.position:
            return None

        side = self.position["side"]
        qty  = self.position["qty"]
        entry = self.position["entry"]

        if side == "LONG":
            pnl = (price - entry) * qty
            self.cash += price * qty

        elif side == "SHORT":
            pnl = (entry - price) * qty
            self.cash += pnl  # realized PL only (paper short)

        self.position = None
        return pnl


    def value(self, price):
        if not self.position:
            return self.cash

        qty = self.position["qty"]
        entry = self.position["entry"]

        if self.position["side"] == "LONG":
            return self.cash + price * qty

        if self.position["side"] == "SHORT":
            unrealized = (entry - price) * qty
            return self.cash + unrealized