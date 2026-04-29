from datetime import date, timedelta
import unittest

from market_scout.indicators import atr, rsi, sma
from market_scout.models import Bar


class IndicatorTests(unittest.TestCase):
    def test_sma_uses_last_period_values(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3), 4)

    def test_rsi_returns_high_value_for_uptrend(self):
        values = [float(i) for i in range(1, 40)]
        self.assertEqual(rsi(values), 100.0)

    def test_atr_returns_positive_value(self):
        start = date(2024, 1, 1)
        bars = [
            Bar(
                date=start + timedelta(days=i),
                open=10 + i,
                high=11 + i,
                low=9 + i,
                close=10.5 + i,
                volume=1000,
            )
            for i in range(20)
        ]
        self.assertGreater(atr(bars), 0)


if __name__ == "__main__":
    unittest.main()
