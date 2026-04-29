from __future__ import annotations

import csv
import hashlib
import math
import random
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import date, timedelta
from pathlib import Path

from .models import Bar


class DataError(RuntimeError):
    pass


class MarketDataProvider(ABC):
    @abstractmethod
    def history(self, symbol: str, *, bars: int) -> list[Bar]:
        raise NotImplementedError


class CsvDataProvider(MarketDataProvider):
    def __init__(self, csv_dir: Path):
        self.csv_dir = csv_dir

    def history(self, symbol: str, *, bars: int) -> list[Bar]:
        path = self.csv_dir / f"{symbol.upper()}.csv"
        if not path.exists():
            path = self.csv_dir / f"{symbol.lower()}.csv"
        if not path.exists():
            raise DataError(f"No CSV found for {symbol} in {self.csv_dir}")
        data = read_bars_csv(path)
        return data[-bars:]


class UploadedCsvDataProvider(MarketDataProvider):
    def __init__(self, files: dict[str, str]):
        self.data_by_symbol = build_uploaded_csv_map(files)

    def history(self, symbol: str, *, bars: int) -> list[Bar]:
        key = symbol.upper()
        if key not in self.data_by_symbol:
            available = ", ".join(sorted(self.data_by_symbol)) or "none"
            raise DataError(f"No uploaded CSV found for {symbol}. Available: {available}")
        return self.data_by_symbol[key][-bars:]


class StooqDataProvider(MarketDataProvider):
    def __init__(self, cache_dir: Path | None = None, api_key: str | None = None):
        self.cache_dir = cache_dir
        self.api_key = api_key.strip() if api_key else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def history(self, symbol: str, *, bars: int) -> list[Bar]:
        cache_path = self._cache_path(symbol)
        if cache_path and cache_path.exists():
            cached = read_bars_csv(cache_path)
            if len(cached) >= min(60, bars):
                return cached[-bars:]

        url = self._url(symbol)
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                body = response.read().decode("utf-8")
        except OSError as exc:
            raise DataError(f"Could not fetch {symbol} from Stooq: {exc}") from exc

        if "get your apikey" in body.lower() or "apikey=" in body.lower():
            raise DataError("Stooq requires an API key. Add it in the Stooq API key field.")

        rows = list(csv.DictReader(body.splitlines()))
        if not rows or "Close" not in rows[0]:
            raise DataError(f"Stooq returned no daily data for {symbol}")

        parsed = parse_csv_rows(rows)
        if cache_path:
            write_bars_csv(cache_path, parsed)
        return parsed[-bars:]

    def _cache_path(self, symbol: str) -> Path | None:
        if not self.cache_dir:
            return None
        digest = hashlib.sha1(symbol.lower().encode("utf-8")).hexdigest()[:12]
        return self.cache_dir / f"{symbol.upper()}-{digest}.csv"

    def _url(self, symbol: str) -> str:
        normalized = symbol.strip().lower()
        if "." not in normalized:
            normalized = f"{normalized}.us"
        query_data = {"s": normalized, "i": "d"}
        if self.api_key:
            query_data["apikey"] = self.api_key
        query = urllib.parse.urlencode(query_data)
        return f"https://stooq.com/q/d/l/?{query}"


class DemoDataProvider(MarketDataProvider):
    """Deterministic synthetic data so the scanner works offline."""

    def history(self, symbol: str, *, bars: int) -> list[Bar]:
        seed = int(hashlib.sha1(symbol.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)
        trend = rng.uniform(-0.0005, 0.0025)
        volatility = rng.uniform(0.008, 0.035)
        base_price = rng.uniform(20.0, 350.0)
        today = date.today()
        data: list[Bar] = []
        close = base_price

        for i in range(max(bars, 180)):
            wave = math.sin(i / rng.uniform(12.0, 35.0)) * volatility * 0.5
            drift = trend + wave
            shock = rng.gauss(0.0, volatility)
            open_price = close * (1.0 + rng.gauss(0.0, volatility * 0.25))
            close = max(1.0, close * (1.0 + drift + shock))
            high = max(open_price, close) * (1.0 + abs(rng.gauss(0.0, volatility * 0.45)))
            low = min(open_price, close) * (1.0 - abs(rng.gauss(0.0, volatility * 0.45)))
            volume = rng.uniform(80_000, 4_000_000) * (1.0 + max(drift, 0.0) * 50)
            data.append(
                Bar(
                    date=today - timedelta(days=max(bars, 180) - i),
                    open=round(open_price, 4),
                    high=round(high, 4),
                    low=round(low, 4),
                    close=round(close, 4),
                    volume=round(volume),
                )
            )
        return data[-bars:]


def read_universe(path: Path) -> list[str]:
    symbols = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        symbols.append(cleaned.split(",")[0].strip().upper())
    return symbols


def read_bars_csv(path: Path) -> list[Bar]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return parse_csv_rows(rows)


def parse_csv_rows(rows: list[dict[str, str]]) -> list[Bar]:
    parsed: list[Bar] = []
    for row in rows:
        try:
            parsed.append(
                Bar(
                    date=date.fromisoformat(row.get("Date") or row.get("date") or ""),
                    open=float(row.get("Open") or row.get("open") or 0),
                    high=float(row.get("High") or row.get("high") or 0),
                    low=float(row.get("Low") or row.get("low") or 0),
                    close=float(row.get("Close") or row.get("close") or 0),
                    volume=float(row.get("Volume") or row.get("volume") or 0),
                )
            )
        except ValueError:
            continue
    return [bar for bar in parsed if bar.close > 0 and bar.high > 0 and bar.low > 0]


def build_uploaded_csv_map(files: dict[str, str]) -> dict[str, list[Bar]]:
    data_by_symbol: dict[str, list[Bar]] = {}
    for filename, content in files.items():
        symbol = Path(filename).stem.strip().upper()
        if not symbol:
            continue
        rows = list(csv.DictReader(content.splitlines()))
        bars = parse_csv_rows(rows)
        if bars:
            data_by_symbol[symbol] = bars
    return data_by_symbol


def write_bars_csv(path: Path, bars: list[Bar]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        for bar in bars:
            writer.writerow([bar.date.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume])
