import tempfile
import unittest

from spot_event_ledger import spot_event_ledger_self_test


class SpotEventLedgerTests(unittest.TestCase):
    def test_long_only_partial_exit_accounting(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(spot_event_ledger_self_test(directory))


if __name__ == "__main__":
    unittest.main()
