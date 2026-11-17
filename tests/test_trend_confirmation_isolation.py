import unittest
from unittest.mock import patch

import pandas as pd

import main


def make_1h_frame(rows=60):
    row = {
        "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0,
        "volume": 1000.0, "ema9": 100.8, "ema21": 100.5,
        "ema50": 100.0, "ema200": 98.0, "adx": 30.0,
        "plus_di": 25.0, "minus_di": 10.0, "rsi": 55.0,
        "rsi_prev": 54.0, "volume_ratio": 2.0, "atr_percent": 1.0,
        "atr": 1.0, "distance_ema21": 0.5, "rolling_vwap": 100.0,
        "obv_slope": 1.0, "bb_width_pct": 2.0, "bb_position": 0.5,
        "macd": 1.0, "macd_signal": 0.5, "macd_hist": 0.5,
        "macd_hist_prev": 0.4, "bearish_candle": False,
        "open_time": "deterministic-test",
    }
    return pd.DataFrame([dict(row) for _ in range(rows)])


class TrendConfirmationIsolationTests(unittest.TestCase):
    def test_1h_trend_builder_does_not_call_30m_or_add_confirmation_score(self):
        frame = make_1h_frame()
        with (
            patch.object(main, "score_30m_confirmation", side_effect=AssertionError("30M called")),
            patch.object(main, "score_main_1h", side_effect=lambda _df, side: {
                "hard_pass": str(side).upper() == "BUY",
                "score": main.MIN_SCORE if str(side).upper() == "BUY" else 0,
                "reasons": ["deterministic 1H-only test"],
            }),
            patch.object(main, "score_btc_regime", return_value={"allowed": True, "score": 0, "reason": "BTC neutral"}),
            patch.object(main, "score_divergence_both_sides", return_value=({"score": 0, "reason": ""}, {"score": 0, "reason": ""})),
            patch.object(main, "score_price_structure", return_value={"score": 0, "bullish": False, "bearish": False}),
            patch.object(main, "get_mtf_context", return_value={}),
            patch.object(main, "mtf_side_adjustment", return_value=(0, [])),
        ):
            result = main.evaluate_final_signal("TESTUSDT", {"1h": frame, "30m": None}, {"combined": "NEUTRAL"})

        self.assertEqual(result.get("signal"), "BUY")
        self.assertEqual(result.get("buy_score"), main.MIN_SCORE)
        diagnostic = result["trend_diagnostic"]
        self.assertIsNone(diagnostic["buy_confirm"])
        self.assertIsNone(diagnostic["sell_confirm"])
        self.assertIs(diagnostic["confirmation_required"], False)
        self.assertEqual(diagnostic["confirmation_timeframe"], "NOT_REQUIRED")

    def test_professional_trend_gate_marks_30m_not_required_and_never_calls_it(self):
        frame = make_1h_frame()
        signal = {
            "signal": "BUY", "signal_mode": "TREND", "signal_timeframe": "1h",
            "score": 100, "rr_tp1": main.TP1_RR, "rr_tp2": main.TP2_RR,
            "reasons": [],
        }
        with patch.object(main, "score_30m_confirmation", side_effect=AssertionError("30M called")):
            main.professional_signal_quality_gate(
                signal, {"1h": frame, "30m": None}, {"combined": "NEUTRAL"}
            )

        breakdown = signal["professional_quality_breakdown"]
        self.assertEqual(breakdown["confirmation_timeframe"], "NOT_REQUIRED")
        self.assertIs(breakdown["confirmation_required"], False)
        self.assertEqual(breakdown["confirmations_lower_tf"], 0)
        self.assertEqual(breakdown["required_lower_tf"], 0)
        self.assertEqual(breakdown["required_30m"], 0)
        ledger = breakdown["component_ledger"]["lower_timeframe_confirmation"]
        self.assertEqual(ledger["status"], "NOT_REQUIRED")
        self.assertEqual(ledger["max"], 0)
        self.assertIn("not required", main.format_confirmation_diagnostic(breakdown).lower())
        self.assertFalse(any("30m confirmation" in r.lower() for r in signal.get("reasons", [])))

    def test_breakout_and_bottom_hunter_still_require_confirmation_data(self):
        frame = make_1h_frame()
        for mode in ("BREAKOUT", "BOTTOM_HUNTER"):
            with self.subTest(mode=mode):
                signal = {
                    "signal": "BUY", "signal_mode": mode, "signal_timeframe": "1h",
                    "score": 100, "rr_tp1": main.TP1_RR, "rr_tp2": main.TP2_RR,
                }
                passed, reasons, _ = main.professional_signal_quality_gate(
                    signal, {"1h": frame, "30m": None}, {"combined": "NEUTRAL"}
                )
                self.assertFalse(passed)
                self.assertIn("required confirmation timeframe data unavailable", reasons)

    def test_btc_combines_bullish_bearish_and_neutral_regimes_and_keeps_mixed_states(self):
        bullish = {"regime": "BULLISH", "score": 4, "bullish": True, "bearish": False}
        bearish = {"regime": "BEARISH", "score": -4, "bullish": False, "bearish": True}
        neutral = {"regime": "NEUTRAL", "score": 0, "bullish": False, "bearish": False}

        cases = (
            (bullish, bullish, "BULLISH"),
            (bearish, bearish, "BEARISH"),
            (neutral, neutral, "NEUTRAL"),
            (bullish, bearish, "MIXED_BULLISH_1H"),
            (bearish, bullish, "MIXED_BEARISH_1H"),
        )
        for one_hour, daily, expected in cases:
            with self.subTest(expected=expected):
                with patch.object(main, "get_btc_1h_regime", return_value=one_hour), patch.object(
                    main, "get_btc_daily_regime", return_value=daily
                ):
                    self.assertEqual(main.get_btc_market_regime()["combined"], expected)

        self.assertTrue(main.score_btc_regime("BUY", {"combined": "BULLISH"})["allowed"])
        self.assertFalse(main.score_btc_regime("SELL", {"combined": "BULLISH"})["allowed"])
        self.assertFalse(main.score_btc_regime("BUY", {"combined": "BEARISH"})["allowed"])
        self.assertTrue(main.score_btc_regime("SELL", {"combined": "BEARISH"})["allowed"])
        for side in ("BUY", "SELL"):
            self.assertTrue(main.score_btc_regime(side, {"combined": "NEUTRAL"})["allowed"])
            self.assertTrue(main.score_btc_regime(side, {"combined": "MIXED_BULLISH_1H"})["allowed"])
            self.assertTrue(main.score_btc_regime(side, {"combined": "MIXED_BEARISH_1H"})["allowed"])


if __name__ == "__main__":
    unittest.main()
