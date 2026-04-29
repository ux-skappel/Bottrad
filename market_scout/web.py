from __future__ import annotations

import argparse
import json
import mimetypes
import os
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .cli import DEFAULT_SYMBOLS, result_to_dict
from .data import CsvDataProvider, DataError, DemoDataProvider, MarketDataProvider, StooqDataProvider
from .indicators import percent_change, previous_sma, rsi, sma
from .risk import RISK_PROFILES, get_profile
from .scanner import MarketScanner, ScannerConfig


PROJECT_ROOT = Path(os.getenv("MARKET_SCOUT_ROOT", Path.cwd())).resolve()
WEB_ROOT = Path(os.getenv("MARKET_SCOUT_WEB_ROOT", PROJECT_ROOT / "web")).resolve()
DEFAULT_CACHE_DIR = Path(os.getenv("MARKET_SCOUT_CACHE_DIR", PROJECT_ROOT / ".cache" / "market_scout")).resolve()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "MarketScoutDashboard/0.1"

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        self.serve_static(parsed.path, head_only=True)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self.send_json({"ok": True, "service": "market-scout"})
            return
        if parsed.path == "/api/profiles":
            self.send_json({"profiles": serialize_profiles()})
            return
        if parsed.path == "/api/defaults":
            self.send_json(
                {
                    "symbols": DEFAULT_SYMBOLS,
                    "symbolsText": "\n".join(DEFAULT_SYMBOLS),
                    "defaults": {
                        "risk": "medium",
                        "source": "demo",
                        "account": 100_000,
                        "top": 15,
                        "bars": 220,
                    },
                }
            )
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/scan":
            self.send_error_json(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        try:
            payload = self.read_json_body()
            response = run_scan(payload)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except Exception as exc:  # Keep the dashboard alive and surface useful errors.
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        self.send_json(response)

    def serve_static(self, request_path: str, *, head_only: bool = False) -> None:
        if request_path in {"", "/"}:
            target = WEB_ROOT / "index.html"
        else:
            cleaned = unquote(request_path).lstrip("/")
            target = WEB_ROOT / cleaned

        try:
            target.resolve().relative_to(WEB_ROOT.resolve())
        except ValueError:
            self.send_error_json(HTTPStatus.FORBIDDEN, "Path outside web root")
            return

        if not target.exists() or not target.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "File not found")
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def read_json_body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0:
            return {}
        if size > 250_000:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(size).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object")
        return payload

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message, "status": status.value}, status)

    def log_message(self, format: str, *args: object) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def run_scan(payload: dict) -> dict:
    source = str(payload.get("source", "demo")).strip().lower()
    if source not in {"demo", "stooq", "csv"}:
        raise ValueError("source must be demo, stooq, or csv")

    risk_name = str(payload.get("risk", "medium"))
    profile = get_profile(risk_name)
    account = clamp_float(payload.get("account", 100_000), 100, 1_000_000_000, "account")
    top = int(clamp_float(payload.get("top", 15), 1, 100, "top"))
    bars = int(clamp_float(payload.get("bars", 220), 80, 1_500, "bars"))
    symbols = parse_symbols(str(payload.get("symbols", "")))
    if not symbols:
        symbols = DEFAULT_SYMBOLS

    provider = build_provider(source, payload)
    scanner = MarketScanner(
        provider=provider,
        profile=profile,
        config=ScannerConfig(account_size=account, lookback_bars=bars, top=top),
    )
    results = scanner.scan(symbols)
    result_dicts = [result_to_dict(result) for result in results]
    regime = build_market_regime(provider, bars=max(220, bars))

    return {
        "scannedAt": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "source": source,
            "risk": profile.name,
            "account": account,
            "top": top,
            "bars": bars,
            "symbols": len(symbols),
        },
        "summary": build_summary(result_dicts),
        "regime": regime,
        "results": result_dicts,
    }


def build_provider(source: str, payload: dict):
    if source == "demo":
        return DemoDataProvider()
    if source == "stooq":
        return StooqDataProvider(cache_dir=DEFAULT_CACHE_DIR)
    csv_dir = payload.get("csvDir")
    if not csv_dir:
        raise ValueError("csvDir is required for csv source")
    return CsvDataProvider(Path(str(csv_dir)).expanduser())


def build_summary(results: list[dict]) -> dict:
    buys = [item for item in results if item["signal"] == "BUY"]
    watches = [item for item in results if item["signal"] == "WATCH"]
    plans = [item["position_plan"] for item in results if item.get("position_plan")]
    total_position_value = sum(plan["position_value"] for plan in plans)
    total_risk = sum(plan["capital_at_risk"] for plan in plans)
    average_score = sum(item["score"] for item in results) / len(results) if results else 0
    return {
        "buyCount": len(buys),
        "watchCount": len(watches),
        "averageScore": round(average_score, 1),
        "totalPositionValue": round(total_position_value, 2),
        "totalCapitalAtRisk": round(total_risk, 2),
        "leader": results[0] if results else None,
    }


def build_market_regime(provider: MarketDataProvider, *, bars: int) -> dict:
    benchmarks = ["SPY", "QQQ", "IWM"]
    items = []
    for symbol in benchmarks:
        try:
            history = provider.history(symbol, bars=bars)
        except DataError as exc:
            items.append({"symbol": symbol, "status": "UNAVAILABLE", "reason": str(exc), "score": 0})
            continue
        item = score_regime_symbol(symbol, history)
        items.append(item)

    usable = [item for item in items if item["status"] != "UNAVAILABLE"]
    if not usable:
        return {
            "state": "UNKNOWN",
            "score": 0,
            "confidence": 0,
            "bias": "No benchmark data available",
            "reason": "SPY, QQQ and IWM could not be read from this data source.",
            "benchmarks": items,
        }

    score = sum(item["score"] for item in usable) / len(usable)
    confidence = min(100, abs(score))
    if score >= 35:
        state = "BULL"
        bias = "Risk-on"
        reason = "Major benchmarks are trading above key trend levels with positive momentum."
    elif score <= -35:
        state = "BEAR"
        bias = "Defensive"
        reason = "Major benchmarks are below key trend levels or momentum is weakening."
    else:
        state = "NEUTRAL"
        bias = "Selective"
        reason = "The market picture is mixed, so position sizing should stay selective."

    return {
        "state": state,
        "score": round(score, 1),
        "confidence": round(confidence, 1),
        "bias": bias,
        "reason": reason,
        "benchmarks": items,
    }


def score_regime_symbol(symbol: str, bars: list) -> dict:
    if len(bars) < 80:
        return {"symbol": symbol, "status": "UNAVAILABLE", "reason": "Not enough history", "score": 0}

    closes = [bar.close for bar in bars]
    close = closes[-1]
    sma50 = sma(closes, 50)
    sma50_prev = previous_sma(closes, 50, 20)
    sma200 = sma(closes, 200)
    current_rsi = rsi(closes)
    momentum20 = percent_change(closes, 20)
    momentum60 = percent_change(closes, 60)

    score = 0.0
    reasons = []

    if sma200:
        if close > sma200:
            score += 30
            reasons.append("above 200D")
        else:
            score -= 30
            reasons.append("below 200D")

    if sma50:
        if close > sma50:
            score += 20
            reasons.append("above 50D")
        else:
            score -= 20
            reasons.append("below 50D")

    if sma50 and sma50_prev:
        if sma50 > sma50_prev:
            score += 15
            reasons.append("50D rising")
        else:
            score -= 10
            reasons.append("50D falling")

    if momentum20 is not None:
        score += 10 if momentum20 > 0 else -10
    if momentum60 is not None:
        score += 10 if momentum60 > 0 else -10

    if current_rsi is not None:
        if current_rsi >= 55:
            score += 8
        elif current_rsi <= 45:
            score -= 8

    if score >= 35:
        status = "BULL"
    elif score <= -35:
        status = "BEAR"
    else:
        status = "NEUTRAL"

    return {
        "symbol": symbol,
        "status": status,
        "score": round(max(-100, min(100, score)), 1),
        "close": round(close, 4),
        "sma50": round(sma50, 4) if sma50 else None,
        "sma200": round(sma200, 4) if sma200 else None,
        "rsi": round(current_rsi, 1) if current_rsi is not None else None,
        "momentum20Pct": round(momentum20 * 100, 1) if momentum20 is not None else None,
        "momentum60Pct": round(momentum60 * 100, 1) if momentum60 is not None else None,
        "reason": ", ".join(reasons[:3]),
    }


def serialize_profiles() -> list[dict]:
    return [
        {
            "name": profile.name,
            "minScore": profile.min_score,
            "riskPerTradePct": profile.risk_per_trade_pct,
            "maxPositionPct": profile.max_position_pct,
            "stopAtrMultiplier": profile.stop_atr_multiplier,
            "targetRMultiple": profile.target_r_multiple,
            "maxAtrPct": profile.max_atr_pct,
            "maxRsi": profile.max_rsi,
            "minAvgVolume": profile.min_avg_volume,
        }
        for profile in RISK_PROFILES.values()
    ]


def parse_symbols(text: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in text.replace(",", "\n").replace(";", "\n").splitlines():
        symbol = raw.strip().upper()
        if not symbol or symbol.startswith("#"):
            continue
        symbol = symbol.split()[0]
        if symbol and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    return symbols[:500]


def clamp_float(value: object, low: float, high: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if number < low or number > high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Market Scout web dashboard.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8765")))
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Market Scout dashboard running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
