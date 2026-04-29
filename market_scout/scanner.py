from __future__ import annotations

from dataclasses import dataclass

from .data import DataError, MarketDataProvider
from .indicators import atr, highest_high, percent_change, previous_sma, rsi, sma
from .models import Bar, ScanResult, Signal
from .risk import RiskProfile, build_position_plan


@dataclass(frozen=True)
class ScannerConfig:
    account_size: float = 100_000.0
    lookback_bars: int = 220
    top: int = 20


class MarketScanner:
    def __init__(self, provider: MarketDataProvider, profile: RiskProfile, config: ScannerConfig):
        self.provider = provider
        self.profile = profile
        self.config = config

    def scan(self, symbols: list[str]) -> list[ScanResult]:
        results = [self._scan_symbol(symbol) for symbol in symbols]
        return sorted(results, key=lambda item: item.score, reverse=True)[: self.config.top]

    def _scan_symbol(self, symbol: str) -> ScanResult:
        try:
            bars = self.provider.history(symbol, bars=self.config.lookback_bars)
        except DataError as exc:
            return self._empty(symbol, Signal.SKIP, str(exc))

        if len(bars) < 80:
            return self._empty(symbol, Signal.SKIP, "Not enough price history")

        score, reasons, metrics = score_bars(bars, self.profile)
        close = bars[-1].close
        current_atr = metrics.get("atr")
        current_rsi = metrics.get("rsi")
        atr_pct = (current_atr / close) if current_atr and close else None

        signal = Signal.WAIT
        if score >= self.profile.min_score:
            signal = Signal.WATCH
        if (
            score >= self.profile.min_score + 8
            and current_atr
            and atr_pct is not None
            and atr_pct <= self.profile.max_atr_pct
            and current_rsi is not None
            and current_rsi <= self.profile.max_rsi
        ):
            signal = Signal.BUY

        plan = None
        if signal in {Signal.BUY, Signal.WATCH} and current_atr:
            plan = build_position_plan(
                account_size=self.config.account_size,
                entry=close,
                atr=current_atr,
                profile=self.profile,
            )

        return ScanResult(
            symbol=symbol,
            signal=signal,
            score=round(score, 1),
            close=round(close, 4),
            rsi=round(current_rsi, 1) if current_rsi is not None else None,
            atr_pct=round(atr_pct, 4) if atr_pct is not None else None,
            sma20=round(metrics["sma20"], 4) if metrics.get("sma20") else None,
            sma50=round(metrics["sma50"], 4) if metrics.get("sma50") else None,
            avg_volume20=round(metrics["avg_volume20"], 0) if metrics.get("avg_volume20") else None,
            plan=plan,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _empty(symbol: str, signal: Signal, reason: str) -> ScanResult:
        return ScanResult(
            symbol=symbol,
            signal=signal,
            score=0.0,
            close=0.0,
            rsi=None,
            atr_pct=None,
            sma20=None,
            sma50=None,
            avg_volume20=None,
            plan=None,
            reasons=(reason,),
        )


def score_bars(bars: list[Bar], profile: RiskProfile) -> tuple[float, list[str], dict[str, float | None]]:
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    close = closes[-1]
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    sma50_prev = previous_sma(closes, 50, 10)
    sma200 = sma(closes, 200)
    current_rsi = rsi(closes)
    current_atr = atr(bars)
    high20 = highest_high(bars, 20)
    high55 = highest_high(bars, 55)
    momentum20 = percent_change(closes, 20)
    momentum60 = percent_change(closes, 60)
    avg_volume20 = sma(volumes, 20)
    latest_volume = volumes[-1]

    score = 0.0
    reasons: list[str] = []

    if sma20 and sma50 and close > sma20 > sma50:
        score += 20
        reasons.append("Price is above rising short/medium trend")
    elif sma20 and sma50 and close > sma50:
        score += 12
        reasons.append("Price is above the 50-day trend")

    if sma50 and sma50_prev and sma50 > sma50_prev:
        score += 12
        reasons.append("50-day trend is rising")

    if sma200 and close > sma200:
        score += 10
        reasons.append("Price is above long-term trend")

    if current_rsi is not None:
        if 45 <= current_rsi <= 65:
            score += 16
            reasons.append("RSI has constructive momentum without being stretched")
        elif 65 < current_rsi <= profile.max_rsi:
            score += 10
            reasons.append("RSI shows strong momentum")
        elif current_rsi < 35:
            score += 4
            reasons.append("RSI is oversold, but needs confirmation")

    if momentum20 is not None and momentum20 > 0:
        score += min(12, momentum20 * 100)
        reasons.append("20-day momentum is positive")

    if momentum60 is not None and momentum60 > 0:
        score += min(10, momentum60 * 60)
        reasons.append("60-day momentum is positive")

    if high20 and close >= high20 * 0.985:
        score += 10
        reasons.append("Price is near a 20-day breakout")

    if high55 and close >= high55 * 0.97:
        score += 8
        reasons.append("Price is close to a 55-day high")

    if avg_volume20 and latest_volume > avg_volume20 * 1.25:
        score += 6
        reasons.append("Volume is expanding")

    if avg_volume20 and avg_volume20 >= profile.min_avg_volume:
        score += 8
        reasons.append("Liquidity passes this risk profile")
    elif avg_volume20:
        score -= 8
        reasons.append("Liquidity is thin for this risk profile")

    if current_atr and close > 0:
        atr_pct = current_atr / close
        if atr_pct <= profile.max_atr_pct * 0.6:
            score += 8
            reasons.append("Volatility is controlled")
        elif atr_pct <= profile.max_atr_pct:
            score += 3
            reasons.append("Volatility is acceptable for this risk profile")
        else:
            score -= 15
            reasons.append("Volatility is above this risk profile")

    if current_rsi is not None and current_rsi > profile.max_rsi:
        score -= 12
        reasons.append("RSI is too extended for this risk profile")

    metrics = {
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "rsi": current_rsi,
        "atr": current_atr,
        "avg_volume20": avg_volume20,
    }
    return max(0.0, min(100.0, score)), reasons[:6], metrics

