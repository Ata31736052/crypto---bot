import csv
import tempfile
import unittest
from pathlib import Path

from research.closed_candle_timing_audit import evaluate, summarize


class ClosedCandleAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.signals = self.root / "signals.csv"
        self.candles = self.root / "candles.csv"
        with self.signals.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "setup", "timestamp"])
            w.writerow(["BTCUSDT", "TREND", "2026-01-01T00:00:00Z"])
            w.writerow(["ETHUSDT", "BOTTOM_HUNTER", "2026-01-01T00:00:00Z"])
        with self.candles.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "timestamp", "open", "high", "low", "close"])
            # The signal candle has an extreme high/low; it must NOT affect MFE/MAE.
            w.writerow(["BTCUSDT", "2026-01-01T00:00:00Z", 100, 150, 50, 100])
            w.writerow(["BTCUSDT", "2026-01-01T01:00:00Z", 100, 110, 95, 105])
            w.writerow(["BTCUSDT", "2026-01-01T02:00:00Z", 105, 112, 98, 110])
            w.writerow(["ETHUSDT", "2026-01-01T00:00:00Z", 20, 25, 15, 20])
            w.writerow(["ETHUSDT", "2026-01-01T01:00:00Z", 20, 22, 19, 21])
            w.writerow(["ETHUSDT", "2026-01-01T02:00:00Z", 21, 23, 20, 22])

    def tearDown(self):
        self.tmp.cleanup()

    def test_uses_only_candles_after_signal_candle(self):
        rows = evaluate(self.signals, self.candles, horizon=2)
        btc = next(r for r in rows if r["symbol"] == "BTCUSDT")
        self.assertAlmostEqual(btc["return_pct"], 10.0)
        self.assertAlmostEqual(btc["mfe_pct"], 12.0)
        self.assertAlmostEqual(btc["mae_pct"], -2.0)

    def test_groups_trend_and_bottom_hunter_separately(self):
        rows = evaluate(self.signals, self.candles, horizon=2)
        summaries = {r["setup"]: r for r in summarize(rows)}
        self.assertEqual(summaries["TREND"]["n"], 1)
        self.assertEqual(summaries["BOTTOM_HUNTER"]["n"], 1)

    def test_rejects_signal_not_aligned_to_closed_candle(self):
        with self.signals.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "setup", "timestamp"])
            w.writerow(["BTCUSDT", "TREND", "2026-01-01T00:30:00Z"])
        with self.assertRaisesRegex(ValueError, "must match a closed candle"):
            evaluate(self.signals, self.candles, horizon=1)

    def test_incomplete_forward_horizon_is_not_counted(self):
        rows = evaluate(self.signals, self.candles, horizon=3)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
