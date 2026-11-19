import tempfile
import unittest

import pandas as pd

from spot_backtest_replay import simulate_spot_buy


class SpotBacktestReplayTests(unittest.TestCase):
    def frame(self, highs, lows, closes):
        start = pd.Timestamp("2026-01-01T01:00:00Z")
        rows = []
        for i, (high, low, close) in enumerate(zip(highs, lows, closes)):
            opened = start + pd.Timedelta(hours=i)
            rows.append({
                "open_time": opened,
                "close_time": opened + pd.Timedelta(hours=1) - pd.Timedelta(milliseconds=1),
                "open": 100.0, "high": high, "low": low, "close": close, "volume": 10.0,
            })
        return pd.DataFrame(rows)

    def signal(self, side="BUY"):
        return {
            "signal": side, "entry": 100.0, "stop_loss": 95.0,
            "tp1": 109.0, "tp2": 112.0, "score": 95, "strength": "STRONG",
        }

    def test_sell_never_opens_short(self):
        result, _ = simulate_spot_buy(
            "ETHUSDT", "2026-01-01T00:59:59Z", 0,
            self.frame([120], [80], [100]), self.signal("SELL"),
            evaluation_time="2026-01-01T03:00:00Z",
        )
        self.assertIsNone(result)

    def test_tp1_partial_then_tp2_later_candle(self):
        candles = self.frame([110, 113], [99, 105], [109, 112])
        trade, _ = simulate_spot_buy(
            "ETHUSDT", "2026-01-01T00:59:59Z", 0, candles, self.signal(),
            fee_bps=0, slippage_bps=0,
            evaluation_time="2026-01-01T04:00:00Z",
        )
        self.assertIsNotNone(trade)
        self.assertEqual([e["event"] for e in trade["exit_events"]], ["TP1_PARTIAL", "TP2_EXIT"])
        self.assertEqual([e["quantity_fraction"] for e in trade["exit_events"]], [0.5, 0.5])
        self.assertAlmostEqual(trade["gross_pct"], 5.25, places=6)

    def test_stop_wins_same_candle_as_tp1(self):
        candles = self.frame([110], [94], [108])
        trade, _ = simulate_spot_buy(
            "ETHUSDT", "2026-01-01T00:59:59Z", 0, candles, self.signal(),
            fee_bps=0, slippage_bps=0,
            evaluation_time="2026-01-01T03:00:00Z",
        )
        self.assertEqual(trade["exit_reason"], "STOP_LOSS")
        self.assertEqual(len(trade["exit_events"]), 1)
        self.assertEqual(trade["exit_events"][0]["quantity_fraction"], 1.0)

    def test_tp1_then_breakeven_stop(self):
        candles = self.frame([110, 111], [99, 99], [109, 100])
        trade, _ = simulate_spot_buy(
            "ETHUSDT", "2026-01-01T00:59:59Z", 0, candles, self.signal(),
            fee_bps=0, slippage_bps=0,
            evaluation_time="2026-01-01T04:00:00Z",
        )
        self.assertEqual([e["event"] for e in trade["exit_events"]], ["TP1_PARTIAL", "BREAK_EVEN_EXIT"])
        self.assertEqual(trade["exit_events"][1]["quantity_fraction"], 0.5)

    def test_incomplete_candle_is_not_used(self):
        candles = self.frame([110], [99], [109])
        trade, _ = simulate_spot_buy(
            "ETHUSDT", "2026-01-01T00:59:59Z", 0, candles, self.signal(),
            fee_bps=0, slippage_bps=0,
            evaluation_time="2026-01-01T01:30:00Z",
        )
        self.assertIsNone(trade)


if __name__ == "__main__":
    unittest.main()
