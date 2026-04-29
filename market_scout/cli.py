from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .data import CsvDataProvider, DemoDataProvider, StooqDataProvider, read_universe
from .models import ScanResult
from .risk import RISK_PROFILES, get_profile
from .scanner import MarketScanner, ScannerConfig


DEFAULT_SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "JPM",
    "XOM",
    "UNH",
    "V",
    "MA",
    "AVGO",
    "LLY",
    "COST",
    "NFLX",
    "AMD",
    "CRM",
    "ADBE",
    "SPY",
    "QQQ",
    "IWM",
]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "profiles":
        print_profiles()
        return 0
    if args.command == "scan":
        return run_scan(args)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-scout",
        description="Scan a market universe for buy candidates with configurable risk profiles.",
    )
    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser("scan", help="scan a symbol universe")
    scan.add_argument("--risk", default="medium", help="low, medium, high, very_high, or Norwegian aliases")
    scan.add_argument("--account", type=float, default=100_000.0, help="account size used for position sizing")
    scan.add_argument("--top", type=int, default=15, help="number of ranked rows to print")
    scan.add_argument("--bars", type=int, default=220, help="historical bars to analyze")
    scan.add_argument("--source", choices=["demo", "stooq", "csv"], default="demo")
    scan.add_argument("--universe", type=Path, help="text/CSV file with one symbol per line")
    scan.add_argument("--csv-dir", type=Path, help="directory with SYMBOL.csv files for --source csv")
    scan.add_argument("--cache-dir", type=Path, default=Path(".cache/market_scout"), help="cache for Stooq data")
    scan.add_argument("--json", action="store_true", help="print JSON instead of a table")

    subparsers.add_parser("profiles", help="show risk profile settings")
    return parser


def run_scan(args: argparse.Namespace) -> int:
    profile = get_profile(args.risk)
    symbols = read_universe(args.universe) if args.universe else DEFAULT_SYMBOLS
    if not symbols:
        print("No symbols to scan.", file=sys.stderr)
        return 2

    provider = build_provider(args)
    scanner = MarketScanner(
        provider=provider,
        profile=profile,
        config=ScannerConfig(account_size=args.account, lookback_bars=args.bars, top=args.top),
    )
    results = scanner.scan(symbols)
    if args.json:
        print(json.dumps([result_to_dict(result) for result in results], indent=2))
    else:
        print_table(results, profile.name)
    return 0


def build_provider(args: argparse.Namespace):
    if args.source == "demo":
        return DemoDataProvider()
    if args.source == "stooq":
        return StooqDataProvider(cache_dir=args.cache_dir)
    if args.source == "csv":
        if not args.csv_dir:
            raise SystemExit("--csv-dir is required when --source csv")
        return CsvDataProvider(args.csv_dir)
    raise SystemExit(f"Unsupported source: {args.source}")


def print_profiles() -> None:
    rows = []
    for profile in RISK_PROFILES.values():
        rows.append(
            [
                profile.name,
                f"{profile.min_score:.0f}",
                f"{profile.risk_per_trade_pct * 100:.1f}%",
                f"{profile.max_position_pct * 100:.0f}%",
                f"{profile.stop_atr_multiplier:.1f} ATR",
                f"{profile.target_r_multiple:.1f}R",
                f"{profile.max_atr_pct * 100:.1f}%",
            ]
        )
    print(format_table(["Risk", "MinScore", "Risk/Trade", "MaxPos", "Stop", "Target", "MaxATR"], rows))


def print_table(results: list[ScanResult], risk_name: str) -> None:
    rows = []
    for result in results:
        plan = result.plan
        rows.append(
            [
                result.symbol,
                result.signal.value,
                f"{result.score:.1f}",
                money(result.close),
                f"{result.rsi:.1f}" if result.rsi is not None else "-",
                f"{result.atr_pct * 100:.1f}%" if result.atr_pct is not None else "-",
                str(plan.shares) if plan else "-",
                money(plan.stop) if plan else "-",
                money(plan.target) if plan else "-",
                "; ".join(result.reasons[:2]),
            ]
        )
    print(f"Risk profile: {risk_name}")
    print(format_table(["Symbol", "Signal", "Score", "Close", "RSI", "ATR%", "Qty", "Stop", "Target", "Why"], rows))


def result_to_dict(result: ScanResult) -> dict:
    plan = result.plan
    return {
        "symbol": result.symbol,
        "signal": result.signal.value,
        "score": result.score,
        "close": result.close,
        "rsi": result.rsi,
        "atr_pct": result.atr_pct,
        "sma20": result.sma20,
        "sma50": result.sma50,
        "avg_volume20": result.avg_volume20,
        "position_plan": plan.__dict__ if plan else None,
        "reasons": list(result.reasons),
    }


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def line(parts: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(parts))

    divider = "  ".join("-" * width for width in widths)
    body = [line(headers), divider]
    body.extend(line(row) for row in rows)
    return "\n".join(body)


def money(value: float) -> str:
    return f"{value:,.2f}"


if __name__ == "__main__":
    raise SystemExit(main())

