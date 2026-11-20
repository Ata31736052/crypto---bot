import io
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import pandas as pd

from historical_universe import (
    _hourly_rolling_quote_volume,
    _read_archive_zip,
    build_point_in_time_universe,
    list_historical_spot_symbols,
    list_daily_spot_symbols,
)


def make_zip(rows):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample.csv", "\n".join(",".join(map(str, row)) for row in rows))
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


class HistoricalUniverseTests(unittest.TestCase):
    def test_s3_listing_paginates_and_includes_three_character_base_symbols(self):
        first = b"""<ListBucketResult>
          <CommonPrefixes><Prefix>data/spot/monthly/klines/OLDUSDT/</Prefix></CommonPrefixes>
          <CommonPrefixes><Prefix>data/spot/monthly/klines/ETHUSDT/</Prefix></CommonPrefixes>
          <CommonPrefixes><Prefix>data/spot/monthly/klines/ETHBTC/</Prefix></CommonPrefixes>
          <IsTruncated>true</IsTruncated><NextContinuationToken>next-page</NextContinuationToken>
        </ListBucketResult>"""
        second = b"""<ListBucketResult>
          <CommonPrefixes><Prefix>data/spot/monthly/klines/DELISTEDUSDT/</Prefix></CommonPrefixes>
          <IsTruncated>false</IsTruncated>
        </ListBucketResult>"""
        client = FakeSession([FakeResponse(first), FakeResponse(second)])
        self.assertEqual(
            list_historical_spot_symbols(session=client),
            ["DELISTEDUSDT", "ETHUSDT", "OLDUSDT"],
        )
        self.assertEqual(client.calls[1][1]["continuation-token"], "next-page")
        daily = FakeSession([FakeResponse(b"""<ListBucketResult>
          <CommonPrefixes><Prefix>data/spot/daily/klines/NEWLISTUSDT/</Prefix></CommonPrefixes>
          <CommonPrefixes><Prefix>data/spot/daily/klines/SOLUSDT/</Prefix></CommonPrefixes>
          <IsTruncated>false</IsTruncated>
        </ListBucketResult>""")])
        self.assertEqual(list_daily_spot_symbols(session=daily), ["NEWLISTUSDT", "SOLUSDT"])

    def test_hourly_archive_parser_handles_microsecond_timestamps(self):
        open_us = int(pd.Timestamp("2026-01-01T00:00:00Z").timestamp() * 1_000_000)
        parsed = _read_archive_zip(
            make_zip([[open_us, 1, 2, 1, 2, 10, open_us + 3_599_999_999, 6_000_000, 3, 5, 3, 0]]),
            "ETHUSDT", "2026-01",
        )
        self.assertEqual(parsed.iloc[0]["open_time"], pd.Timestamp("2026-01-01T00:00:00Z"))
        self.assertEqual(float(parsed.iloc[0]["quote_volume"]), 6_000_000)

    def test_hourly_rolling_volume_uses_only_previous_24_closed_bars(self):
        opens = pd.date_range("2026-01-01T01:00:00Z", periods=25, freq="h")
        frame = pd.DataFrame({
            "open_time": opens,
            "quote_volume": [250_000] * 24 + [10_000_000],
        })
        snapshots = pd.date_range("2026-01-02T01:00:00Z", periods=2, freq="h")
        rolling = _hourly_rolling_quote_volume(frame, snapshots)
        self.assertEqual(float(rolling.loc[snapshots[0]]), 6_000_000)
        self.assertEqual(float(rolling.loc[snapshots[1]]), 15_750_000)
        self.assertIn(snapshots[1], rolling.index)

    def test_missing_hour_invalidates_24h_window(self):
        opens = pd.date_range("2026-01-01T01:00:00Z", periods=25, freq="h").delete(8)
        frame = pd.DataFrame({"open_time": opens, "quote_volume": [1_000_000] * len(opens)})
        snapshots = pd.date_range("2026-01-02T01:00:00Z", periods=2, freq="h")
        rolling = _hourly_rolling_quote_volume(frame, snapshots)
        self.assertTrue(rolling.empty)

    def test_hourly_universe_ranks_rolling_volume_excludes_btc_and_waits_for_24_bars(self):
        opens = pd.date_range("2026-01-01T01:00:00Z", periods=25, freq="h")
        data = {
            "ETHUSDT": pd.DataFrame({"open_time": opens, "quote_volume": [250_000] * 24 + [10_000_000]}),
            "SOLUSDT": pd.DataFrame({"open_time": opens, "quote_volume": [300_000] * 25}),
            "BTCUSDT": pd.DataFrame({"open_time": opens, "quote_volume": [99_000_000] * 25}),
            # Newly listed pair has fewer than 24 bars at the first snapshot.
            "NEWUSDT": pd.DataFrame({
                "open_time": opens[1:],
                "quote_volume": [1_000_000] * 24,
            }),
        }

        def fake_download(symbol, month, cache_dir, **kwargs):
            return data.get(symbol, pd.DataFrame(columns=["open_time", "quote_volume"]))

        with tempfile.TemporaryDirectory() as cache:
            with patch("historical_universe.list_historical_spot_symbols", return_value=list(data)), patch(
                "historical_universe.list_daily_spot_symbols", return_value=[]
            ), patch("historical_universe._download_hourly_month", side_effect=fake_download):
                result = build_point_in_time_universe(
                    pd.Timestamp("2026-01-02T00:00:00Z"),
                    pd.Timestamp("2026-01-02T02:00:00Z"),
                    min_quote_volume_usdt=5_000_000,
                    max_symbols=2,
                    cache_dir=cache,
                    is_directional_base=lambda base: True,
                )

        first = result["hourly_snapshots"]["2026-01-02T01:00:00Z"]
        second = result["hourly_snapshots"]["2026-01-02T02:00:00Z"]
        self.assertEqual(first, ["SOLUSDT", "ETHUSDT"])
        self.assertEqual(second, ["NEWUSDT", "ETHUSDT"])
        self.assertNotIn("BTCUSDT", result["symbols"])
        self.assertEqual(result["snapshot_cadence"], "hourly_at_next_1h_open")
        self.assertEqual(result["selection_method"], "previous_24_closed_1h_quote_volume_ranked_at_each_hour")
        self.assertTrue(result["lookahead_free"])
        self.assertEqual(result["candidate_symbol_count"], 3)

    def test_empty_history_is_not_forward_filled(self):
        start = pd.Timestamp("2026-01-02T00:00:00Z")
        end = pd.Timestamp("2026-01-02T02:00:00Z")
        with tempfile.TemporaryDirectory() as cache:
            with patch("historical_universe.list_historical_spot_symbols", return_value=["ETHUSDT"]), patch(
                "historical_universe._download_hourly_month",
                return_value=pd.DataFrame(columns=["open_time", "quote_volume"]),
            ):
                with self.assertRaisesRegex(RuntimeError, "universe is empty"):
                    build_point_in_time_universe(start, end, cache_dir=cache)

if __name__ == "__main__":
    unittest.main()
