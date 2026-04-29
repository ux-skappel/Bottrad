import unittest

from market_scout.data import DemoDataProvider, UploadedCsvDataProvider
from market_scout.web import build_market_regime, parse_symbols, run_scan


class WebTests(unittest.TestCase):
    def test_parse_symbols_deduplicates_common_separators(self):
        self.assertEqual(parse_symbols("aapl, msft\nAAPL; qqq"), ["AAPL", "MSFT", "QQQ"])

    def test_run_scan_returns_dashboard_payload(self):
        payload = {
            "source": "demo",
            "risk": "medium",
            "account": 25_000,
            "top": 3,
            "bars": 220,
            "symbols": "AAPL\nMSFT\nQQQ\nSPY",
        }
        response = run_scan(payload)
        self.assertEqual(len(response["results"]), 3)
        self.assertIn("summary", response)
        self.assertIn("regime", response)
        self.assertEqual(response["config"]["risk"], "medium")

    def test_market_regime_returns_state(self):
        regime = build_market_regime(DemoDataProvider(), bars=220)
        self.assertIn(regime["state"], {"BULL", "BEAR", "NEUTRAL", "UNKNOWN"})
        self.assertEqual(len(regime["benchmarks"]), 3)

    def test_csv_upload_provider_reads_symbol_files(self):
        csv_text = "\n".join(
            [
                "Date,Open,High,Low,Close,Volume",
                "2026-01-01,10,11,9,10.5,1000",
                "2026-01-02,10.5,12,10,11.5,1100",
            ]
        )
        provider = UploadedCsvDataProvider({"AAPL.csv": csv_text})
        bars = provider.history("AAPL", bars=10)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[-1].close, 11.5)

    def test_run_scan_accepts_uploaded_csv_payload(self):
        rows = ["Date,Open,High,Low,Close,Volume"]
        for day in range(1, 90):
            rows.append(f"2026-01-{(day % 28) + 1:02d},{day},{day + 1},{day - 1},{day + 0.5},1000000")
        response = run_scan(
            {
                "source": "csv",
                "risk": "medium",
                "account": 25_000,
                "top": 1,
                "bars": 80,
                "symbols": "AAPL",
                "csvFiles": {"AAPL.csv": "\n".join(rows)},
            }
        )
        self.assertEqual(response["results"][0]["symbol"], "AAPL")


if __name__ == "__main__":
    unittest.main()
