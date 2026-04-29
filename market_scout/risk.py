from __future__ import annotations

from .models import PositionPlan, RiskProfile


RISK_PROFILES: dict[str, RiskProfile] = {
    "low": RiskProfile(
        name="low",
        min_score=75.0,
        risk_per_trade_pct=0.005,
        max_position_pct=0.10,
        stop_atr_multiplier=2.5,
        target_r_multiple=2.0,
        max_atr_pct=0.055,
        max_rsi=68.0,
        min_avg_volume=500_000,
    ),
    "medium": RiskProfile(
        name="medium",
        min_score=68.0,
        risk_per_trade_pct=0.010,
        max_position_pct=0.15,
        stop_atr_multiplier=2.0,
        target_r_multiple=2.5,
        max_atr_pct=0.080,
        max_rsi=74.0,
        min_avg_volume=250_000,
    ),
    "high": RiskProfile(
        name="high",
        min_score=60.0,
        risk_per_trade_pct=0.020,
        max_position_pct=0.25,
        stop_atr_multiplier=1.8,
        target_r_multiple=3.0,
        max_atr_pct=0.120,
        max_rsi=82.0,
        min_avg_volume=100_000,
    ),
    "very_high": RiskProfile(
        name="very_high",
        min_score=52.0,
        risk_per_trade_pct=0.040,
        max_position_pct=0.35,
        stop_atr_multiplier=1.5,
        target_r_multiple=4.0,
        max_atr_pct=0.200,
        max_rsi=88.0,
        min_avg_volume=25_000,
    ),
}

PROFILE_ALIASES = {
    "lav": "low",
    "forsiktig": "low",
    "middels": "medium",
    "balansert": "medium",
    "hoy": "high",
    "aggressiv": "high",
    "svart_hoy": "very_high",
    "spekulativ": "very_high",
}


def get_profile(name: str) -> RiskProfile:
    key = name.strip().lower().replace("-", "_")
    key = PROFILE_ALIASES.get(key, key)
    if key not in RISK_PROFILES:
        options = ", ".join(sorted(RISK_PROFILES | PROFILE_ALIASES))
        raise ValueError(f"Unknown risk profile '{name}'. Choose one of: {options}")
    return RISK_PROFILES[key]


def build_position_plan(
    *,
    account_size: float,
    entry: float,
    atr: float,
    profile: RiskProfile,
) -> PositionPlan | None:
    if account_size <= 0 or entry <= 0 or atr <= 0:
        return None

    stop_distance = atr * profile.stop_atr_multiplier
    stop = max(0.01, entry - stop_distance)
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return None

    capital_at_risk = account_size * profile.risk_per_trade_pct
    max_position_value = account_size * profile.max_position_pct
    risk_sized_shares = int(capital_at_risk // risk_per_share)
    value_sized_shares = int(max_position_value // entry)
    shares = max(0, min(risk_sized_shares, value_sized_shares))
    if shares == 0:
        return None

    actual_risk = shares * risk_per_share
    position_value = shares * entry
    target = entry + (risk_per_share * profile.target_r_multiple)
    return PositionPlan(
        entry=round(entry, 4),
        stop=round(stop, 4),
        target=round(target, 4),
        shares=shares,
        capital_at_risk=round(actual_risk, 2),
        position_value=round(position_value, 2),
        portfolio_pct=round(position_value / account_size, 4),
    )

