import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from research.historical_signal_generator import closed_asof_slice, evaluate_barriers


class HistoricalSignalGeneratorTests(unittest.TestCase):
    def test_asof_slice_excludes_candle_not_closed_at_decision(self):
        decision = pd.Timestamp("2026-01-01T02:00:00Z")
        frame = pd.DataFrame([
            {"close_time": pd.Timestamp("2026-01-01T00:59:59.999Z"), "close": 100},
            {"close_time": pd.Timestamp("2026-01-01T01:59:59.999Z"), "close": 101},
            {"close_time": pd.Timestamp("2026-01-01T02:59:59.999Z"), "close": 102},
        ])
        out = closed_asof_slice(frame, decision)
        self.assertEqual(out["close"].tolist(), [100, 101])

    def test_same_candle_sl_tp1_resolves_stop_first_for_buy(self):
        signal = {"side": "BUY", "actual_entry": 100, "stop_loss": 95, "tp1": 105}
        future = pd.DataFrame([
            {"open": 100, "high": 106, "low": 94, "close": 101},
        ] * 8)
        out = evaluate_barriers(signal, future, 8, 0.4)
        self.assertEqual(out["event"], "SL_FIRST_SAME_CANDLE")
        self.assertAlmostEqual(out["net_return_pct"], -5.4)

    def test_sell_side_stop_and_target_order(self):
        signal = {"side": "SELL", "actual_entry": 100, "stop_loss": 105, "tp1": 95}
        future = pd.DataFrame([
            {"open": 100, "high": 104, "low": 94, "close": 99},
        ] * 8)
        out = evaluate_barriers(signal, future, 8, 0.4)
        self.assertEqual(out["event"], "TP1")
        self.assertAlmostEqual(out["net_return_pct"], (100 / 95 - 1) * 100 - 0.4)

    def test_incomplete_horizon_fails_closed(self):
        signal = {"side": "BUY", "actual_entry": 100, "stop_loss": 95, "tp1": 105}
        future = pd.DataFrame([{"open": 100, "high": 101, "low": 99, "close": 100}] * 7)
        out = evaluate_barriers(signal, future, 8, 0.4)
        self.assertEqual(out["event"], "INCOMPLETE_WINDOW")
        self.assertIsNone(out["net_return_pct"])


if __name__ == "__main__":
    unittest.main()
