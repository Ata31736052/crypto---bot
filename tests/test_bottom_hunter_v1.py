import math
import unittest

from bottom_hunter_v1.core import find_early_warning, find_signal
from scripts.bottom_hunter_v1_backtest import size_position


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
    def test_position_size_never_exceeds_spot_cash_including_entry_fee(self):
        equity, entry, stop, fee_bps = 100.0, 10.0, 9.0, 10.0
        qty = size_position(equity, entry, stop, 0.01, 1000.0, fee_bps)
        self.assertLessEqual(qty * entry * (1 + fee_bps / 10000), equity + 1e-9)
        self.assertLessEqual(qty * (entry - stop), equity * 0.01 + 1e-9)

    def test_position_size_respects_notional_cap(self):
        qty = size_position(1000.0, 10.0, 9.99, 0.01, 50.0, 10.0)
        self.assertLessEqual(qty * 10.0, 50.0 + 1e-9)

    def test_invalid_position_inputs_return_zero(self):
        self.assertEqual(size_position(0, 10, 9, 0.01, 100, 10), 0.0)
        self.assertEqual(size_position(100, 10, 11, 0.01, 100, 10), 0.0)

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

    def test_early_warning_is_separate_from_tradable_entry(self):
        bars = make_bars()
        # Remove the bullish break: this must remain a warning, not an entry.
        bars[-1]["close"] = bars[-1]["open"] * 0.999
        warning = find_early_warning(bars, "ETHUSDT", min_decline_pct=1.0)
        self.assertIsNotNone(warning)
        self.assertEqual(warning["status"], "WATCH")
        self.assertFalse(warning["tradable"])
        self.assertNotIn("stop_loss", warning)
        self.assertNotIn("take_profit_1", warning)
        self.assertIsNone(find_signal(bars, "ETHUSDT", min_decline_pct=1.0))

    def test_early_warning_requires_real_decline(self):
        bars = make_bars()
        # Flatten the pre-signal history so there is no meaningful decline.
        for bar in bars[:-1]:
            bar["open"] = 100.0
            bar["high"] = 100.2
            bar["low"] = 99.8
            bar["close"] = 100.0
        self.assertIsNone(find_early_warning(bars, "ETHUSDT", min_decline_pct=1.0))


if __name__ == "__main__":
    unittest.main()
