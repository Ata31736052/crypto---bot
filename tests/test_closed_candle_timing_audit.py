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
            # Signal candle extremes must not affect forward MFE/MAE.
            w.writerow(["BTCUSDT", "2026-01-01T00:00:00Z", 100, 150, 50, 100])
            w.writerow(["BTCUSDT", "2026-01-01T01:00:00Z", 100, 110, 95, 98])
            w.writerow(["BTCUSDT", "2026-01-01T02:00:00Z", 98, 112, 97, 101])
            w.writerow(["BTCUSDT", "2026-01-01T03:00:00Z", 101, 103, 99, 102])
            w.writerow(["ETHUSDT", "2026-01-01T00:00:00Z", 20, 25, 15, 20])
            w.writerow(["ETHUSDT", "2026-01-01T01:00:00Z", 20, 22, 19, 21])
            w.writerow(["ETHUSDT", "2026-01-01T02:00:00Z", 21, 23, 20, 22])
            w.writerow(["ETHUSDT", "2026-01-01T03:00:00Z", 22, 24, 21, 23])

    def tearDown(self):
        self.tmp.cleanup()

    def test_uses_only_candles_after_signal_and_applies_costs(self):
        rows = evaluate(self.signals, self.candles, horizons=(1, 2), fee_bps_per_side=10, slippage_bps_per_side=5)
        btc_2h = next(r for r in rows if r["symbol"] == "BTCUSDT" and r["horizon_hours"] == 2)
        self.assertAlmostEqual(btc_2h["gross_return_pct"], 1.0)
        self.assertAlmostEqual(btc_2h["net_return_pct"], 0.7)
        self.assertAlmostEqual(btc_2h["mfe_pct"], 12.0)
        self.assertAlmostEqual(btc_2h["mae_pct"], -5.0)

    def test_groups_trend_and_bottom_hunter_by_horizon(self):
        rows = evaluate(self.signals, self.candles, horizons=(1, 2))
        summaries = {(r["setup"], r["horizon_hours"]): r for r in summarize(rows)}
        self.assertEqual(summaries[("TREND", 1)]["n"], 1)
        self.assertEqual(summaries[("BOTTOM_HUNTER", 2)]["n"], 1)

    def test_rejects_signal_not_aligned_to_closed_candle(self):
        with self.signals.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "setup", "timestamp"])
            w.writerow(["BTCUSDT", "TREND", "2026-01-01T00:30:00Z"])
        with self.assertRaisesRegex(ValueError, "must match a closed candle"):
            evaluate(self.signals, self.candles, horizons=(1,))

    def test_incomplete_forward_horizon_is_not_counted(self):
        rows = evaluate(self.signals, self.candles, horizons=(4,))
        self.assertEqual(rows, [])

    def test_hourly_gaps_invalidate_later_horizons(self):
        with self.candles.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "timestamp", "open", "high", "low", "close"])
            w.writerow(["BTCUSDT", "2026-01-01T00:00:00Z", 100, 101, 99, 100])
            w.writerow(["BTCUSDT", "2026-01-01T01:00:00Z", 100, 101, 99, 100])
            w.writerow(["BTCUSDT", "2026-01-01T03:00:00Z", 100, 101, 99, 100])
        with self.signals.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "setup", "timestamp"])
            w.writerow(["BTCUSDT", "TREND", "2026-01-01T00:00:00Z"])
        rows = evaluate(self.signals, self.candles, horizons=(1, 2))
        self.assertEqual([r["horizon_hours"] for r in rows], [1])

    def test_recovery_time_after_adverse_close(self):
        rows = evaluate(self.signals, self.candles, horizons=(3,), fee_bps_per_side=0, slippage_bps_per_side=0)
        btc = next(r for r in rows if r["symbol"] == "BTCUSDT")
        self.assertEqual(btc["recovery_to_entry_hours"], 2)

    def test_recovery_after_horizon_is_not_counted(self):
        rows = evaluate(self.signals, self.candles, horizons=(1, 2), fee_bps_per_side=0, slippage_bps_per_side=0)
        btc_1h = next(r for r in rows if r["symbol"] == "BTCUSDT" and r["horizon_hours"] == 1)
        btc_2h = next(r for r in rows if r["symbol"] == "BTCUSDT" and r["horizon_hours"] == 2)
        self.assertIsNone(btc_1h["recovery_to_entry_hours"])
        self.assertEqual(btc_2h["recovery_to_entry_hours"], 2)


if __name__ == "__main__":
    unittest.main()
