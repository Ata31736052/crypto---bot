import unittest

from spot_position_manager import (
    apply_exit_transition,
    build_open_spot_position,
    evaluate_closed_candle,
    spot_exit_self_test,
)


class SpotPositionManagerTests(unittest.TestCase):
    def test_self_test_suite(self):
        self.assertTrue(spot_exit_self_test())

    def test_tp1_then_tp2(self):
        signal = {
            "symbol": "BTCUSDT", "signal": "BUY", "entry": 100,
            "stop_loss": 95, "tp1": 109, "tp2": 112,
            "position_quantity": 1, "candle_time": "2026-01-01T00:00:00+00:00",
        }
        position = build_open_spot_position(signal, "2026-01-01T01:00:00+00:00")
        first = evaluate_closed_candle(position, {
            "open_time": "2026-01-01T01:00:00+00:00", "high": 109.5,
            "low": 99.5, "close": 109,
        })
        position = apply_exit_transition(position, first)
        second = evaluate_closed_candle(position, {
            "open_time": "2026-01-01T02:00:00+00:00", "high": 113,
            "low": 101, "close": 112.5,
        })
        self.assertEqual(second["event"], "TP2_EXIT")
        self.assertTrue(second["closed"])


if __name__ == "__main__":
    unittest.main()
