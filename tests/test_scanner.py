import unittest

from market_scout.data import DemoDataProvider
from market_scout.risk import get_profile
from market_scout.scanner import MarketScanner, ScannerConfig


class ScannerTests(unittest.TestCase):
    def test_scanner_ranks_symbols(self):
        scanner = MarketScanner(
            provider=DemoDataProvider(),
            profile=get_profile("medium"),
            config=ScannerConfig(account_size=50_000, lookback_bars=220, top=5),
        )
        results = scanner.scan(["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ"])
        self.assertEqual(len(results), 5)
        self.assertEqual(results, sorted(results, key=lambda item: item.score, reverse=True))


if __name__ == "__main__":
    unittest.main()
