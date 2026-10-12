import unittest
from datetime import datetime, timedelta, timezone

from research.replay_historical_entry_locations import analyze_signal, classify_setup, atr_from_closed_candles


def sample_candles(count=80):
    start = datetime(2026, 9, 25, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        close = 100 + (i % 5) * 0.2
        open_time = start + timedelta(hours=i)
        rows.append({
            "open_time": open_time,
            "close_time": open_time + timedelta(hours=1) - timedelta(milliseconds=1),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
        })
    # Make a confirmed overhead swing high well before the signal.
    for idx, high in ((35, 105.0), (36, 108.0), (37, 120.0), (38, 107.0), (39, 105.0)):
        rows[idx]["high"] = high
    return rows


class HistoricalLocationReplayTests(unittest.TestCase):
    def test_setup_classification_is_explicitly_heuristic(self):
        self.assertEqual(classify_setup({"reasons": ["Near 72H low", "RSI recovering"]}), "BOTTOM_HUNTER_HEURISTIC")
        self.assertEqual(classify_setup({"reasons": ["EMA9 > EMA21"]}), "TREND_HEURISTIC")

    def test_only_pre_signal_closed_candles_are_used(self):
        candles = sample_candles()
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 119.5, "reasons": ["EMA9 > EMA21"],
        }, candles)
        self.assertEqual(result["status"], "ASSESSED")
        self.assertNotEqual(result["historical_resistance"], 120.0 if candles[37]["close_time"] > signal_time else -1)

    def test_insufficient_closed_history_fails_closed(self):
        candles = sample_candles(10)
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY",
            "timestamp": (candles[5]["open_time"] + timedelta(minutes=30)).isoformat(),
            "entry": 100, "reasons": [],
        }, candles)
        self.assertEqual(result["status"], "INSUFFICIENT_CLOSED_HISTORY")

    def test_invalid_entry_fails_closed(self):
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY",
            "timestamp": datetime(2026, 9, 29, tzinfo=timezone.utc).isoformat(),
            "entry": 0, "reasons": [],
        }, sample_candles())
        self.assertEqual(result["status"], "INVALID_ENTRY")


if __name__ == "__main__":
    unittest.main()
