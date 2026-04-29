from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class Signal(str, Enum):
    BUY = "BUY"
    WATCH = "WATCH"
    WAIT = "WAIT"
    SKIP = "SKIP"


@dataclass(frozen=True)
class RiskProfile:
    name: str
    min_score: float
    risk_per_trade_pct: float
    max_position_pct: float
    stop_atr_multiplier: float
    target_r_multiple: float
    max_atr_pct: float
    max_rsi: float
    min_avg_volume: float


@dataclass(frozen=True)
class PositionPlan:
    entry: float
    stop: float
    target: float
    shares: int
    capital_at_risk: float
    position_value: float
    portfolio_pct: float


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    signal: Signal
    score: float
    close: float
    rsi: float | None
    atr_pct: float | None
    sma20: float | None
    sma50: float | None
    avg_volume20: float | None
    plan: PositionPlan | None
    reasons: tuple[str, ...]

