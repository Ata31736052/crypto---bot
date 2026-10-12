import unittest

from research.entry_exit_location_audit import assess_trade_location


def candles_with_resistance(high=110.0, count=12):
    rows = []
    for i in range(count):
        close = 98.0 + (i % 2) * 0.1
        rows.append({"open": close, "high": close + 0.4, "low": close - 0.4, "close": close})
    rows[4] = {"open": 98, "high": 99, "low": 97, "close": 98}
    rows[5] = {"open": 99, "high": 100, "low": 97.5, "close": 99}
    rows[6] = {"open": 100, "high": high, "low": 98, "close": min(100.5, high)}
    rows[7] = {"open": 99, "high": 100, "low": 97.5, "close": 99}
    rows[8] = {"open": 98, "high": 99, "low": 97, "close": 98}
    rows[-1] = {"open": 100, "high": 101, "low": 99, "close": 100}
    return rows


class EntryExitLocationAuditTests(unittest.TestCase):
    def test_buy_near_historical_resistance_is_rejected(self):
        result = assess_trade_location(candles_with_resistance(110), entry=109, atr=1, side="BUY")
        self.assertFalse(result["accepted"])
        self.assertIn("BUY_TOO_CLOSE_TO_HISTORICAL_RESISTANCE", result["rejection_reasons"])
        self.assertEqual(result["historical_resistance"], 110)

    def test_signal_candle_high_cannot_become_its_own_resistance(self):
        rows = candles_with_resistance(110)
        rows[-1] = {"open": 100, "high": 150, "low": 99, "close": 100}
        result = assess_trade_location(rows, entry=100, atr=2, side="BUY")
        self.assertNotEqual(result["historical_resistance"], 150)

    def test_buy_with_clear_resistance_room_can_pass_if_targets_fit(self):
        rows = candles_with_resistance(120)
        result = assess_trade_location(rows, entry=100, atr=1, side="BUY", max_stop_pct=13)
        self.assertTrue(result["accepted"], result["rejection_reasons"])
        self.assertAlmostEqual(result["rr_tp1"], 1.8)
        self.assertAlmostEqual(result["rr_tp2"], 2.4)

    def test_target_cannot_be_planned_through_resistance(self):
        rows = candles_with_resistance(102.5)
        result = assess_trade_location(rows, entry=100, atr=1, side="BUY")
        self.assertFalse(result["accepted"])
        self.assertIn("TP1_BLOCKED_BY_RESISTANCE", result["rejection_reasons"])

    def test_sell_near_support_is_rejected(self):
        rows = candles_with_resistance(120)
        rows[4] = {"open": 94, "high": 96, "low": 92, "close": 94}
        rows[5] = {"open": 93, "high": 95, "low": 91, "close": 93}
        rows[6] = {"open": 94, "high": 96, "low": 90, "close": 94}
        rows[7] = {"open": 97, "high": 99, "low": 95, "close": 97}
        rows[8] = {"open": 99, "high": 101, "low": 97, "close": 99}
        rows[-1] = {"open": 100, "high": 101, "low": 99, "close": 100}
        result = assess_trade_location(rows, entry=91, atr=1, side="SELL")
        self.assertFalse(result["accepted"])
        self.assertIn("SELL_TOO_CLOSE_TO_HISTORICAL_SUPPORT", result["rejection_reasons"])

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            assess_trade_location(candles_with_resistance(), entry=0, atr=1)
        with self.assertRaises(ValueError):
            assess_trade_location(candles_with_resistance(), entry=100, atr=0)


if __name__ == "__main__":
    unittest.main()
