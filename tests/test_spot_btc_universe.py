import unittest

from historical_backtest import filter_backtest_symbols


class BtcContextUniverseTests(unittest.TestCase):
    def test_btc_context_is_excluded_from_directional_universe(self):
        eligible, excluded = filter_backtest_symbols(["BTC", "BTCUSDT"])
        self.assertEqual(eligible, [])
        self.assertEqual(excluded, ["BTCUSDT"])


if __name__ == "__main__":
    unittest.main()
