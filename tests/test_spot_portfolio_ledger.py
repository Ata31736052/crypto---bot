import tempfile
import unittest

import portfolio_ledger
import historical_backtest


class SpotPortfolioLedgerTests(unittest.TestCase):
    def test_spot_sell_closes_inventory_without_opening_short(self):
        with tempfile.TemporaryDirectory() as output_dir:
            self.assertIsNone(portfolio_ledger.portfolio_ledger_self_test(output_dir))

    def test_rolling_historical_warmup_allows_later_eligibility(self):
        self.assertTrue(historical_backtest.rolling_warmup_self_test())


if __name__ == "__main__":
    unittest.main()
