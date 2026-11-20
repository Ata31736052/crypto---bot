import io
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import pandas as pd
import historical_backtest

from historical_universe import (
    _read_daily_archive,
    build_point_in_time_universe,
    list_historical_spot_symbols,
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
    def test_s3_listing_paginates_and_returns_historical_usdt_pairs(self):
        first = b"""<ListBucketResult>
          <CommonPrefixes><Prefix>data/spot/monthly/klines/OLDUSDT/</Prefix></CommonPrefixes>
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
            ["DELISTEDUSDT", "OLDUSDT"],
        )
        self.assertEqual(client.calls[1][1]["continuation-token"], "next-page")

    def test_archive_parser_handles_microsecond_timestamps(self):
        open_us = int(pd.Timestamp("2026-01-01T00:00:00Z").timestamp() * 1_000_000)
        parsed = _read_daily_archive(make_zip([[open_us, 1, 2, 1, 2, 10, open_us + 86_399_999_999, 6_000_000, 3, 5, 3, 0]]), "ETHUSDT", "2026-01")
        self.assertEqual(parsed.iloc[0]["day"], pd.Timestamp("2026-01-01T00:00:00Z"))
        self.assertEqual(float(parsed.iloc[0]["quote_volume"]), 6_000_000)

    def test_universe_uses_only_previous_closed_day_and_top_n(self):
        start = pd.Timestamp("2026-01-02T12:00:00Z")
        end = pd.Timestamp("2026-01-03T12:00:00Z")
        jan1 = pd.Timestamp("2026-01-01T00:00:00Z")
        jan2 = pd.Timestamp("2026-01-02T00:00:00Z")
        data = {
            "ETHUSDT": pd.DataFrame({"day": [jan1, jan2], "quote_volume": [8_000_000, 1_000_000]}),
            "SOLUSDT": pd.DataFrame({"day": [jan1, jan2], "quote_volume": [6_000_000, 9_000_000]}),
            "BTCUSDT": pd.DataFrame({"day": [jan1, jan2], "quote_volume": [99_000_000, 99_000_000]}),
            "NEWUSDT": pd.DataFrame({"day": [jan2], "quote_volume": [100_000_000]}),
        }
        def fake_download(symbol, month, cache_dir):
            return data.get(symbol, pd.DataFrame(columns=["day", "quote_volume"]))
        with tempfile.TemporaryDirectory() as cache:
            with patch("historical_universe.list_historical_spot_symbols", return_value=list(data)), patch(
                "historical_universe._download_daily_month", side_effect=fake_download
            ):
                result = build_point_in_time_universe(
                    start, end, min_quote_volume_usdt=5_000_000, max_symbols=1,
                    cache_dir=cache, is_directional_base=lambda base: True,
                )
        self.assertEqual(result["daily_snapshots"]["2026-01-02T00:00:00Z"], ["ETHUSDT"])
        self.assertEqual(result["daily_snapshots"]["2026-01-03T00:00:00Z"], ["SOLUSDT"])
        self.assertNotIn("BTCUSDT", result["symbols"])
        self.assertNotIn("NEWUSDT", result["daily_snapshots"]["2026-01-03T00:00:00Z"])


    def test_delisted_symbol_archive_fallback_reads_microsecond_daily_file(self):
        open_us = int(pd.Timestamp("2026-10-01T00:00:00Z").timestamp() * 1_000_000)
        row = [open_us, 100, 102, 99, 101, 10, open_us + 3_599_999_999, 1000, 5, 4, 400, 0]
        monthly_404 = FakeResponse(status_code=404)
        daily_zip = FakeResponse(make_zip([row]))
        fake_session = FakeSession([monthly_404, daily_zip])
        original = historical_backtest.SESSION
        try:
            historical_backtest.SESSION = fake_session
            rows = historical_backtest.fetch_vision_archive_rows(
                "DELISTEDUSDT", "1h",
                int(pd.Timestamp("2026-10-01T00:00:00Z").timestamp() * 1000),
                int(pd.Timestamp("2026-10-01T23:59:00Z").timestamp() * 1000),
            )
        finally:
            historical_backtest.SESSION = original
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], open_us // 1000)
        self.assertEqual(rows[0][6], (open_us + 3_599_999_999) // 1000)
        self.assertIn("/daily/klines/DELISTEDUSDT/1h/", fake_session.calls[1][0])

    def test_missing_previous_day_volume_is_not_forward_filled(self):
        start = pd.Timestamp("2026-01-02T00:00:00Z")
        end = pd.Timestamp("2026-01-03T00:00:00Z")
        frame = pd.DataFrame({
            "day": [pd.Timestamp("2026-01-01T00:00:00Z")],
            "quote_volume": [6_000_000],
        })
        with tempfile.TemporaryDirectory() as cache:
            with patch("historical_universe.list_historical_spot_symbols", return_value=["ETHUSDT"]), patch(
                "historical_universe._download_daily_month", return_value=frame
            ):
                result = build_point_in_time_universe(start, end, cache_dir=cache)
        self.assertEqual(result["daily_snapshots"]["2026-01-02T00:00:00Z"], ["ETHUSDT"])
        self.assertEqual(result["daily_snapshots"]["2026-01-03T00:00:00Z"], [])


if __name__ == "__main__":
    unittest.main()
