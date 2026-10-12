import unittest
from datetime import datetime, timedelta, timezone

from research.replay_historical_entry_locations import analyze_signal, classify_setup, atr_from_closed_candles, policy_accepts, prior_move_metrics, simulate_pullback_reentry, evaluate_recorded_barriers


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
        metrics = prior_move_metrics(prior, 117.5, "BUY", 2.0)
        self.assertEqual(metrics["progress_bucket_72h"], "LATE_THIRD")
        self.assertGreater(metrics["directional_progress_72h_pct"], 66.6)
        self.assertEqual(metrics["prior_return_12h_pct"], (
            prior[-1]["close"] / prior[-13]["close"] - 1
        ) * 100)
        # SELL progress is directional: closer to the recent low means later progress.
        sell_metrics = prior_move_metrics(prior, 101.0, "SELL", 2.0)
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

    def test_sell_forward_outcomes_are_direction_adjusted(self):
        candles = sample_candles(80)
        for idx in range(61, 80):
            close = 110.0 + (idx - 61) * 0.1
            candles[idx]["close"] = close
            candles[idx]["high"] = close + 1
            candles[idx]["low"] = close - 1
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        result = analyze_signal({
            "symbol": "TEST", "signal": "SELL", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "reasons": ["EMA9 < EMA21"],
        }, candles)
        self.assertEqual(result["status"], "ASSESSED")
        self.assertLess(result["close_return_1h_pct"], 0)
        self.assertLess(result["mfe_1h_pct"], 0)
        self.assertLess(result["mae_1h_pct"], 0)

    def test_pullback_reclaim_requires_pullback_then_later_reclaim(self):
        candles = sample_candles(80)
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        for idx in range(61, 80):
            close = 100.0
            candles[idx]["open"] = close
            candles[idx]["close"] = close
            candles[idx]["high"] = 101.0
            candles[idx]["low"] = 99.5
        candles[61]["low"] = 96.0  # 0.5 ATR pullback
        candles[62]["close"] = 100.5  # reclaim only after pullback candle
        candles[62]["high"] = 101.0
        base = analyze_signal({
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "reasons": ["EMA9 > EMA21"],
        }, candles)
        result = simulate_pullback_reentry({
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "reasons": ["EMA9 > EMA21"],
        }, candles, base)
        self.assertEqual(result["pullback_status"], "ENTERED_AFTER_PULLBACK_RECLAIM")
        self.assertGreaterEqual(result["pullback_entry"], 100.0)
        self.assertEqual(result["pullback_entry_time"], candles[62]["close_time"].isoformat())

    def test_pullback_reclaim_reports_no_pullback(self):
        candles = sample_candles(80)
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        for idx in range(61, 80):
            candles[idx]["open"] = 100.0
            candles[idx]["close"] = 101.0
            candles[idx]["high"] = 102.0
            candles[idx]["low"] = 100.0
        signal = {
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "reasons": ["EMA9 > EMA21"],
        }
        base = analyze_signal(signal, candles)
        result = simulate_pullback_reentry(signal, candles, base)
        self.assertEqual(result["pullback_status"], "NO_PULLBACK_WITHIN_WAIT")

    def test_same_candle_stop_and_tp1_is_conservatively_stop_first(self):
        candles = sample_candles(80)
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        # Following candle touches both the stored stop and TP1.
        candles[61]["low"] = 97.0
        candles[61]["high"] = 104.0
        signal = {
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "stop_loss": 98.0, "tp1": 103.0, "reasons": [],
        }
        result = evaluate_recorded_barriers(signal, candles)
        self.assertEqual(result["barrier_8h_status"], "STOP_FIRST_AMBIGUOUS_CANDLE")
        self.assertTrue(result["barrier_8h_ambiguous"])
        self.assertAlmostEqual(result["barrier_8h_return_pct"], -2.0)

    def test_first_tp1_hit_is_recorded(self):
        candles = sample_candles(80)
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        candles[61]["low"] = 99.0
        candles[61]["high"] = 104.0
        signal = {
            "symbol": "TEST", "signal": "BUY", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "stop_loss": 98.0, "tp1": 103.0, "reasons": [],
        }
        result = evaluate_recorded_barriers(signal, candles)
        self.assertEqual(result["barrier_8h_status"], "TP1")
        self.assertAlmostEqual(result["barrier_8h_return_pct"], 3.0)

    def test_sell_barrier_order_and_direction_are_respected(self):
        candles = sample_candles(80)
        signal_time = candles[60]["open_time"] + timedelta(minutes=30)
        candles[61]["low"] = 96.0
        candles[61]["high"] = 101.0
        signal = {
            "symbol": "TEST", "signal": "SELL", "timestamp": signal_time.isoformat(),
            "entry": 100.0, "stop_loss": 102.0, "tp1": 97.0, "reasons": [],
        }
        result = evaluate_recorded_barriers(signal, candles)
        self.assertEqual(result["barrier_8h_status"], "TP1")
        self.assertAlmostEqual(result["barrier_8h_return_pct"], 3.0)

    def test_missing_recorded_levels_fail_closed(self):
        candles = sample_candles(80)
        signal = {
            "symbol": "TEST", "signal": "BUY",
            "timestamp": (candles[60]["open_time"] + timedelta(minutes=30)).isoformat(),
            "entry": 100.0,
        }
        result = evaluate_recorded_barriers(signal, candles)
        self.assertEqual(result["barrier_8h_status"], "LEVELS_UNAVAILABLE")

    def test_invalid_entry_fails_closed(self):
        result = analyze_signal({
            "symbol": "TEST", "signal": "BUY",
            "timestamp": datetime(2026, 9, 29, tzinfo=timezone.utc).isoformat(),
            "entry": 0, "reasons": [],
        }, sample_candles())
        self.assertEqual(result["status"], "INVALID_ENTRY")


if __name__ == "__main__":
    unittest.main()
