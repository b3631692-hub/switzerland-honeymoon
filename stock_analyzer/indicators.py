"""Technical indicators for stock analysis."""
from typing import List, Tuple
import math


def sma(prices: List[float], period: int) -> List[float | None]:
    result = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        result[i] = sum(prices[i - period + 1:i + 1]) / period
    return result


def ema(prices: List[float], period: int) -> List[float | None]:
    result: List[float | None] = [None] * len(prices)
    if len(prices) < period:
        return result
    k = 2 / (period + 1)
    result[period - 1] = sum(prices[:period]) / period
    for i in range(period, len(prices)):
        result[i] = prices[i] * k + result[i - 1] * (1 - k)
    return result


def rsi(prices: List[float], period: int = 14) -> List[float | None]:
    result: List[float | None] = [None] * len(prices)
    if len(prices) < period + 1:
        return result
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - 100 / (1 + rs)

    for i in range(period + 1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gain = max(delta, 0)
        loss = max(-delta, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - 100 / (1 + rs)
    return result


def macd(prices: List[float], fast: int = 12, slow: int = 26, signal_period: int = 9) -> Tuple[List[float | None], List[float | None], List[float | None]]:
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd_line: List[float | None] = [None] * len(prices)
    for i in range(len(prices)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    macd_values = [v for v in macd_line if v is not None]
    signal_line_raw = ema(macd_values, signal_period) if len(macd_values) >= signal_period else [None] * len(macd_values)

    signal_out: List[float | None] = [None] * len(prices)
    histogram: List[float | None] = [None] * len(prices)
    idx = 0
    for i in range(len(prices)):
        if macd_line[i] is not None:
            if idx < len(signal_line_raw):
                signal_out[i] = signal_line_raw[idx]
                if signal_out[i] is not None:
                    histogram[i] = macd_line[i] - signal_out[i]
            idx += 1
    return macd_line, signal_out, histogram


def bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Tuple[List[float | None], List[float | None], List[float | None]]:
    middle = sma(prices, period)
    upper: List[float | None] = [None] * len(prices)
    lower: List[float | None] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        mean = middle[i]
        variance = sum((x - mean) ** 2 for x in window) / period
        std = math.sqrt(variance)
        upper[i] = mean + num_std * std
        lower[i] = mean - num_std * std
    return upper, middle, lower


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float | None]:
    result: List[float | None] = [None] * len(closes)
    if len(closes) < 2:
        return result
    true_ranges = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return result
    result[period] = sum(true_ranges[:period]) / period
    for i in range(period + 1, len(closes)):
        tr_idx = i - 1
        if tr_idx < len(true_ranges):
            result[i] = (result[i - 1] * (period - 1) + true_ranges[tr_idx]) / period
    return result


def kdj(highs: List[float], lows: List[float], closes: List[float], n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[List[float | None], List[float | None], List[float | None]]:
    k_line: List[float | None] = [None] * len(closes)
    d_line: List[float | None] = [None] * len(closes)
    j_line: List[float | None] = [None] * len(closes)

    if len(closes) < n:
        return k_line, d_line, j_line

    prev_k = 50.0
    prev_d = 50.0
    for i in range(n - 1, len(closes)):
        window_high = max(highs[i - n + 1:i + 1])
        window_low = min(lows[i - n + 1:i + 1])
        if window_high == window_low:
            rsv = 50.0
        else:
            rsv = (closes[i] - window_low) / (window_high - window_low) * 100
        k = (2 / m1) * prev_k + (1 / m1) * rsv
        d = (2 / m2) * prev_d + (1 / m2) * k
        j = 3 * k - 2 * d
        k_line[i] = k
        d_line[i] = d
        j_line[i] = j
        prev_k = k
        prev_d = d
    return k_line, d_line, j_line


def obv(closes: List[float], volumes: List[float]) -> List[float]:
    result = [0.0] * len(closes)
    if not closes:
        return result
    result[0] = volumes[0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            result[i] = result[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            result[i] = result[i - 1] - volumes[i]
        else:
            result[i] = result[i - 1]
    return result


def vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float]) -> List[float | None]:
    result: List[float | None] = [None] * len(closes)
    cum_vol = 0.0
    cum_tp_vol = 0.0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3
        cum_vol += volumes[i]
        cum_tp_vol += tp * volumes[i]
        if cum_vol > 0:
            result[i] = cum_tp_vol / cum_vol
    return result


def support_resistance(closes: List[float], window: int = 20) -> Tuple[List[float], List[float]]:
    supports = []
    resistances = []
    for i in range(window, len(closes) - window):
        if closes[i] == min(closes[i - window:i + window + 1]):
            supports.append(closes[i])
        if closes[i] == max(closes[i - window:i + window + 1]):
            resistances.append(closes[i])
    return supports, resistances
