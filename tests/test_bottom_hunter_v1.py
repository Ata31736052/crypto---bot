import math
import unittest

from bottom_hunter_v1.core import find_signal


def make_bars():
    bars = []
    price = 100.0
    for _ in range(22):
        nxt = price * 0.995
        bars.append({
            "open": price,
            "high": price * 1.002,
            "low": nxt * 0.997,
            "close": nxt,
            "volume": 100.0,
        })
        price = nxt
    previous_high = bars[-1]["high"]
    open_price = bars[-1]["close"]
    close = previous_high * 1.004
    bars.append({
        "open": open_price,
        "high": close * 1.002,
        "low": open_price * 0.995,
        "close": close,
        "volume": 120.0,
    })
    return bars


class BottomHunterTests(unittest.TestCase):
    def test_valid_rebound_returns_levels(self):
        signal = find_signal(make_bars(), "ETHUSDT", min_decline_pct=1.0)
        self.assertIsNotNone(signal)
        self.assertGreater(signal["signal_close"], signal["stop_loss"])
        self.assertGreater(signal["take_profit_1"], signal["signal_close"])
        self.assertGreater(signal["take_profit_2"], signal["take_profit_1"])

    def test_no_breakout_means_no_signal(self):
        bars = make_bars()
        bars[-1]["close"] = bars[-1]["open"] * 0.999
        self.assertIsNone(find_signal(bars, "ETHUSDT", min_decline_pct=1.0))

    def test_non_finite_data_is_rejected(self):
        bars = make_bars()
        bars[-1]["close"] = math.nan
        self.assertIsNone(find_signal(bars, "ETHUSDT", min_decline_pct=1.0))

    def test_insufficient_history_is_rejected(self):
        self.assertIsNone(find_signal(make_bars()[:10], "ETHUSDT"))


if __name__ == "__main__":
    unittest.main()
