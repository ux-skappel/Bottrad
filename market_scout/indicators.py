from __future__ import annotations

from collections.abc import Sequence

from .models import Bar


def sma(values: Sequence[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def previous_sma(values: Sequence[float], period: int, offset: int) -> float | None:
    end = len(values) - offset
    if period <= 0 or end < period:
        return None
    return sum(values[end - period : end]) / period


def rsi(values: Sequence[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None

    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(bars: Sequence[Bar], period: int = 14) -> float | None:
    if len(bars) <= period:
        return None

    true_ranges = []
    for i in range(1, len(bars)):
        current = bars[i]
        previous = bars[i - 1]
        true_range = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        true_ranges.append(true_range)

    if len(true_ranges) < period:
        return None

    current_atr = sum(true_ranges[:period]) / period
    for true_range in true_ranges[period:]:
        current_atr = ((current_atr * (period - 1)) + true_range) / period
    return current_atr


def highest_high(bars: Sequence[Bar], period: int) -> float | None:
    if len(bars) < period:
        return None
    return max(bar.high for bar in bars[-period:])


def percent_change(values: Sequence[float], period: int) -> float | None:
    if len(values) <= period:
        return None
    start = values[-period - 1]
    end = values[-1]
    if start == 0:
        return None
    return (end / start) - 1.0

