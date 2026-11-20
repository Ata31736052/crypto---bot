import unittest

import main
from historical_backtest import filter_backtest_symbols


class BtcContextUniverseTests(unittest.TestCase):
    def test_btc_context_helper_normalizes_base_and_pair_symbols(self):
        self.assertTrue(main.is_btc_context_symbol("BTC"))
        self.assertTrue(main.is_btc_context_symbol("BTCUSDT"))
        self.assertFalse(main.is_btc_context_symbol("ETHUSDT"))

    def test_backtest_universe_excludes_btc_and_normalizes_pairs(self):
        eligible, excluded = filter_backtest_symbols(
            ["BTC", "BTCUSDT", "ETH", "SOLUSDT"]
        )
        self.assertEqual(eligible, ["ETHUSDT", "SOLUSDT"])
        self.assertEqual(excluded, ["BTCUSDT"])

    def test_backtest_universe_does_not_drop_directional_assets(self):
        eligible, excluded = filter_backtest_symbols(["ETHUSDT", "BNBUSDT"])
        self.assertEqual(eligible, ["ETHUSDT", "BNBUSDT"])
        self.assertEqual(excluded, [])


if __name__ == "__main__":
    unittest.main()
