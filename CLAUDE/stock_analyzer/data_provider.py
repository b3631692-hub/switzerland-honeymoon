"""Data provider: fetch stock data from Yahoo Finance or generate sample data."""
import json
import math
import random
import os
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta


def generate_sample_data(
    symbol: str = "SAMPLE",
    days: int = 252,
    start_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0003,
    seed: int | None = None,
) -> Dict[str, Any]:
    if seed is not None:
        random.seed(seed)

    dates = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    price = start_price
    base_date = datetime(2025, 1, 2)

    for i in range(days):
        current_date = base_date + timedelta(days=i)
        if current_date.weekday() >= 5:
            continue

        daily_return = random.gauss(trend, volatility)
        open_price = price
        close_price = price * (1 + daily_return)

        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility * 0.5)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility * 0.5)))
        volume = int(random.gauss(5_000_000, 1_500_000))
        volume = max(volume, 100_000)

        dates.append(current_date.strftime("%Y-%m-%d"))
        opens.append(round(open_price, 2))
        highs.append(round(high_price, 2))
        lows.append(round(low_price, 2))
        closes.append(round(close_price, 2))
        volumes.append(volume)

        price = close_price

    return {
        "symbol": symbol,
        "dates": dates,
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "volumes": volumes,
    }


def generate_trending_data(symbol: str = "TREND", days: int = 252) -> Dict[str, Any]:
    return generate_sample_data(symbol, days, start_price=50.0, volatility=0.025, trend=0.001, seed=42)


def generate_volatile_data(symbol: str = "VOLATILE", days: int = 252) -> Dict[str, Any]:
    return generate_sample_data(symbol, days, start_price=200.0, volatility=0.04, trend=0.0, seed=123)


def generate_bearish_data(symbol: str = "BEAR", days: int = 252) -> Dict[str, Any]:
    return generate_sample_data(symbol, days, start_price=150.0, volatility=0.025, trend=-0.0008, seed=456)


PRESETS = {
    "uptrend": generate_trending_data,
    "volatile": generate_volatile_data,
    "bearish": generate_bearish_data,
    "default": lambda: generate_sample_data(seed=99),
}


try:
    import urllib.request
    import urllib.parse

    def fetch_yahoo_data(symbol: str, period: str = "1y") -> Dict[str, Any] | None:
        period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
        days = period_map.get(period, 365)
        end = int(datetime.now().timestamp())
        start = int((datetime.now() - timedelta(days=days)).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?period1={start}&period2={end}&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            chart = data["chart"]["result"][0]
            timestamps = chart["timestamp"]
            quote = chart["indicators"]["quote"][0]
            dates = [datetime.fromtimestamp(t).strftime("%Y-%m-%d") for t in timestamps]
            return {
                "symbol": symbol,
                "dates": dates,
                "opens": [round(v, 2) if v else 0 for v in quote["open"]],
                "highs": [round(v, 2) if v else 0 for v in quote["high"]],
                "lows": [round(v, 2) if v else 0 for v in quote["low"]],
                "closes": [round(v, 2) if v else 0 for v in quote["close"]],
                "volumes": [int(v) if v else 0 for v in quote["volume"]],
            }
        except Exception:
            return None

except ImportError:
    def fetch_yahoo_data(symbol: str, period: str = "1y") -> Dict[str, Any] | None:
        return None


def load_csv(filepath: str) -> Dict[str, Any] | None:
    if not os.path.exists(filepath):
        return None
    dates, opens, highs, lows, closes, volumes = [], [], [], [], [], []
    with open(filepath, "r") as f:
        header = f.readline().strip().lower().split(",")
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 6:
                continue
            row = dict(zip(header, parts))
            dates.append(row.get("date", ""))
            opens.append(float(row.get("open", 0)))
            highs.append(float(row.get("high", 0)))
            lows.append(float(row.get("low", 0)))
            closes.append(float(row.get("close", 0)))
            volumes.append(int(float(row.get("volume", 0))))
    symbol = os.path.basename(filepath).replace(".csv", "").upper()
    return {"symbol": symbol, "dates": dates, "opens": opens, "highs": highs, "lows": lows, "closes": closes, "volumes": volumes}
