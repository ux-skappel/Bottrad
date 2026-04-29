import unittest

from market_scout.data import DemoDataProvider
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


if __name__ == "__main__":
    unittest.main()
