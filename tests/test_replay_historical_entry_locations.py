import unittest
from datetime import datetime, timedelta, timezone

from research.replay_historical_entry_locations import analyze_signal, classify_setup, atr_from_closed_candles, policy_accepts, prior_move_metrics


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
    # Make a confirmed overhead swing high when the fixture is long enough.
    if count > 40:
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
        candles[60]["high"] = 200.0  # this candle has not closed at signal time
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 119.5, "reasons": ["EMA9 > EMA21"],
        }, candles)
        self.assertEqual(result["status"], "ASSESSED")
        self.assertNotEqual(result["historical_resistance"], 200.0)

    def test_move_stage_metrics_use_only_prior_candles(self):
        candles = sample_candles(100)
        # Flat-ish rising history gives an interpretable range-position check.
        prior = [c for c in candles if c["close_time"] <= candles[80]["open_time"]]
        prior[-1]["close"] = 105.0
        metrics = prior_move_metrics(prior, 110.0, "BUY", 2.0)
        self.assertEqual(metrics["progress_bucket_72h"], "LATE_THIRD")
        self.assertGreater(metrics["directional_progress_72h_pct"], 66.6)
        self.assertEqual(metrics["prior_return_12h_pct"], (
            prior[-1]["close"] / prior[-13]["close"] - 1
        ) * 100)
        # SELL progress is directional: closer to the recent low means later progress.
        sell_metrics = prior_move_metrics(prior, 91.0, "SELL", 2.0)
        self.assertGreater(sell_metrics["directional_progress_72h_pct"], 66.6)

    def test_move_stage_metrics_mark_short_windows_unavailable(self):
        metrics = prior_move_metrics(sample_candles(20), 100.0, "BUY", 1.0)
        self.assertEqual(metrics["progress_bucket_72h"], "UNAVAILABLE")
        self.assertEqual(metrics["directional_progress_72h_pct"], "")
        self.assertEqual(metrics["prior_return_48h_pct"], "")

    def test_insufficient_closed_history_fails_closed(self):
        candles = sample_candles(10)
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY",
            "timestamp": (candles[5]["open_time"] + timedelta(minutes=30)).isoformat(),
            "entry": 100, "reasons": [],
        }, candles)
        self.assertEqual(result["status"], "INSUFFICIENT_CLOSED_HISTORY")


    def test_tp1_candidate_can_ignore_tp2_only_if_tp1_is_clear(self):
        row = {
            "status": "ASSESSED",
            "location_gate_accepted": False,
            "room_to_obstacle_atr": 1.2,
            "structural_stop_pct": 2.0,
            "rejection_reasons": "TP2_BLOCKED_BY_RESISTANCE",
        }
        self.assertFalse(policy_accepts(row, "STRICT_1P5_ATR_BOTH_TARGETS"))
        self.assertTrue(policy_accepts(row, "TP1_ONLY_1P0_ATR"))
        self.assertTrue(policy_accepts(row, "TP1_ONLY_0P5_ATR"))

    def test_tp1_candidate_still_rejects_obstructed_first_target(self):
        row = {
            "status": "ASSESSED",
            "location_gate_accepted": False,
            "room_to_obstacle_atr": 2.0,
            "rejection_reasons": "TP1_BLOCKED_BY_RESISTANCE;TP2_BLOCKED_BY_RESISTANCE",
        }
        self.assertFalse(policy_accepts(row, "TP1_ONLY_1P0_ATR"))

    def test_tp1_candidate_respects_obstacle_room_and_stop_width(self):
        row = {
            "status": "ASSESSED",
            "location_gate_accepted": False,
            "room_to_obstacle_atr": 0.7,
            "rejection_reasons": "",
        }
        self.assertFalse(policy_accepts(row, "TP1_ONLY_1P0_ATR"))
        self.assertTrue(policy_accepts(row, "TP1_ONLY_0P5_ATR"))
        row["rejection_reasons"] = "STRUCTURAL_STOP_TOO_WIDE"
        self.assertFalse(policy_accepts(row, "TP1_ONLY_0P5_ATR"))

    def test_invalid_entry_fails_closed(self):
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY",
            "timestamp": datetime(2026, 9, 29, tzinfo=timezone.utc).isoformat(),
            "entry": 0, "reasons": [],
        }, sample_candles())
        self.assertEqual(result["status"], "INVALID_ENTRY")


if __name__ == "__main__":
    unittest.main()
