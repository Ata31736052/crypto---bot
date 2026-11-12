import unittest
from unittest.mock import patch

import pandas as pd

import main
from spot_position_manager import build_open_spot_position


class SpotSignalIntegrationTests(unittest.TestCase):
    def make_buy(self):
        return {
            "symbol": "ETHUSDT", "signal": "BUY", "score": 96,
            "strength": "STRONG", "signal_mode": "TREND", "signal_timeframe": "1h",
            "candle_time": "2026-01-01T00:00:00+00:00",
            "price": 100.0, "entry": 100.0, "stop_loss": 95.0,
            "tp1": 109.0, "tp2": 112.0, "position_quantity": 2.0,
            "reasons": ["closed 1H setup"],
        }

    def test_buy_delivery_opens_one_tracked_spot_position(self):
        state = main.get_empty_state()
        history = []
        with patch("main.send_signal_to_telegram", return_value=True), \
             patch("main.save_bot_state", return_value=True), \
             patch("main.save_signal_history", return_value=True):
            result = main.process_signal(self.make_buy(), state, history)
        self.assertTrue(result["sent"])
        self.assertIn("ETHUSDT", state["spot_positions"])
        self.assertEqual(state["spot_positions"]["ETHUSDT"]["remaining_quantity"], 2.0)
        self.assertEqual(len(history), 1)

    def test_buy_does_not_pyramid_same_symbol(self):
        state = main.get_empty_state()
        state["spot_positions"]["ETHUSDT"] = build_open_spot_position(
            self.make_buy(), "2026-01-01T01:00:00+00:00"
        )
        with patch("main.send_signal_to_telegram") as send:
            result = main.process_signal(self.make_buy(), state, [])
        self.assertEqual(result["reason"], "POSITION_ALREADY_OPEN")
        send.assert_not_called()

    def test_sell_without_open_buy_never_sends_short_alert(self):
        state = main.get_empty_state()
        sell = {**self.make_buy(), "signal": "SELL", "candle_time": "2026-01-01T02:00:00+00:00"}
        with patch("main.send_telegram_message") as send:
            result = main.process_signal(sell, state, [])
        self.assertEqual(result["reason"], "SPOT_SHORT_DISABLED_NO_OPEN_POSITION")
        send.assert_not_called()

    def test_sell_closes_only_an_existing_spot_buy(self):
        state = main.get_empty_state()
        state["spot_positions"]["ETHUSDT"] = build_open_spot_position(
            self.make_buy(), "2026-01-01T01:00:00+00:00"
        )
        sell = {**self.make_buy(), "signal": "SELL", "price": 108.0,
                "candle_time": "2026-01-01T02:00:00+00:00"}
        with patch("main.send_telegram_message", return_value=True), \
             patch("main.save_bot_state", return_value=True):
            result = main.process_signal(sell, state, [])
        self.assertTrue(result["sent"])
        self.assertNotIn("ETHUSDT", state["spot_positions"])
        self.assertEqual(state["spot_position_events"][-1]["event"], "SELL_SIGNAL_EXIT")


class SpotExitMonitorIntegrationTests(unittest.TestCase):
    def test_stop_alert_closes_position_only_after_telegram_success(self):
        buy = {
            "symbol": "ETHUSDT", "signal": "BUY", "entry": 100.0,
            "stop_loss": 95.0, "tp1": 109.0, "tp2": 112.0,
            "position_quantity": 2.0, "candle_time": "2026-01-01T00:00:00+00:00",
        }
        position = build_open_spot_position(buy, "2026-01-01T01:00:00+00:00")
        frame = pd.DataFrame([{
            "open_time": pd.Timestamp("2026-01-01T01:00:00Z"),
            "close_time": pd.Timestamp("2026-01-01T01:59:59.999Z"),
            "high": 101.0, "low": 94.0, "close": 96.0,
            "ema21": 99.0, "macd_hist": -0.1,
        }])
        state = {"spot_positions": {"ETHUSDT": position}, "spot_position_events": []}
        with patch("main.get_klines", return_value=frame), \
             patch("main.add_indicators", return_value=frame), \
             patch("main.send_telegram_message", return_value=True), \
             patch("main.save_bot_state", return_value=True):
            stats = main.manage_open_spot_positions(state)
        self.assertEqual(stats["events"], 1)
        self.assertNotIn("ETHUSDT", state["spot_positions"])
        self.assertEqual(state["spot_position_events"][-1]["event"], "STOP_LOSS")

    def test_failed_telegram_exit_is_retried_without_advancing_state(self):
        buy = {
            "symbol": "ETHUSDT", "signal": "BUY", "entry": 100.0,
            "stop_loss": 95.0, "tp1": 109.0, "tp2": 112.0,
            "position_quantity": 2.0, "candle_time": "2026-01-01T00:00:00+00:00",
        }
        position = build_open_spot_position(buy, "2026-01-01T01:00:00+00:00")
        original_last = position["last_checked_candle"]
        frame = pd.DataFrame([{
            "open_time": pd.Timestamp("2026-01-01T01:00:00Z"),
            "close_time": pd.Timestamp("2026-01-01T01:59:59.999Z"),
            "high": 101.0, "low": 94.0, "close": 96.0,
            "ema21": 99.0, "macd_hist": -0.1,
        }])
        state = {"spot_positions": {"ETHUSDT": position}, "spot_position_events": []}
        with patch("main.get_klines", return_value=frame), \
             patch("main.add_indicators", return_value=frame), \
             patch("main.send_telegram_message", return_value=False):
            stats = main.manage_open_spot_positions(state)
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(state["spot_positions"]["ETHUSDT"]["last_checked_candle"], original_last)
        self.assertEqual(state["spot_position_events"], [])


if __name__ == "__main__":
    unittest.main()
