"""Trading strategies with buy/sell signal generation."""
from typing import List, Dict, Any
from .indicators import sma, ema, rsi, macd, bollinger_bands, kdj


class Signal:
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    def __init__(self, action: str, strength: float, reason: str, index: int):
        self.action = action
        self.strength = min(max(strength, 0.0), 1.0)
        self.reason = reason
        self.index = index

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "strength": round(self.strength, 3),
            "reason": self.reason,
            "index": self.index,
        }


class GoldenCrossStrategy:
    """SMA crossover: golden cross (buy) / death cross (sell)."""

    def __init__(self, short_period: int = 10, long_period: int = 30):
        self.short_period = short_period
        self.long_period = long_period
        self.name = f"SMA CrossOver({short_period}/{long_period})"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        short_sma = sma(closes, self.short_period)
        long_sma = sma(closes, self.long_period)
        signals = []
        for i in range(1, len(closes)):
            if all(v is not None for v in [short_sma[i], long_sma[i], short_sma[i - 1], long_sma[i - 1]]):
                if short_sma[i - 1] <= long_sma[i - 1] and short_sma[i] > long_sma[i]:
                    gap = (short_sma[i] - long_sma[i]) / long_sma[i]
                    signals.append(Signal(Signal.BUY, min(0.5 + gap * 20, 1.0), f"黃金交叉 SMA{self.short_period}↑SMA{self.long_period}", i))
                elif short_sma[i - 1] >= long_sma[i - 1] and short_sma[i] < long_sma[i]:
                    gap = (long_sma[i] - short_sma[i]) / long_sma[i]
                    signals.append(Signal(Signal.SELL, min(0.5 + gap * 20, 1.0), f"死亡交叉 SMA{self.short_period}↓SMA{self.long_period}", i))
        return signals


class RSIStrategy:
    """RSI overbought/oversold reversals."""

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.name = f"RSI({period}) [{oversold}/{overbought}]"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        rsi_values = rsi(closes, self.period)
        signals = []
        for i in range(1, len(closes)):
            if rsi_values[i] is not None and rsi_values[i - 1] is not None:
                if rsi_values[i - 1] < self.oversold and rsi_values[i] >= self.oversold:
                    strength = (self.oversold - rsi_values[i - 1]) / self.oversold
                    signals.append(Signal(Signal.BUY, min(0.6 + strength, 1.0), f"RSI 超賣反彈 ({rsi_values[i-1]:.1f}→{rsi_values[i]:.1f})", i))
                elif rsi_values[i - 1] > self.overbought and rsi_values[i] <= self.overbought:
                    strength = (rsi_values[i - 1] - self.overbought) / (100 - self.overbought)
                    signals.append(Signal(Signal.SELL, min(0.6 + strength, 1.0), f"RSI 超買回落 ({rsi_values[i-1]:.1f}→{rsi_values[i]:.1f})", i))
        return signals


class MACDStrategy:
    """MACD signal line crossover."""

    def __init__(self, fast: int = 12, slow: int = 26, signal_period: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period
        self.name = f"MACD({fast}/{slow}/{signal_period})"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        macd_line, signal_line, histogram = macd(closes, self.fast, self.slow, self.signal_period)
        signals = []
        for i in range(1, len(closes)):
            if all(v is not None for v in [histogram[i], histogram[i - 1]]):
                if histogram[i - 1] <= 0 and histogram[i] > 0:
                    signals.append(Signal(Signal.BUY, min(0.5 + abs(histogram[i]) * 2, 1.0), "MACD 柱狀翻正 (多頭訊號)", i))
                elif histogram[i - 1] >= 0 and histogram[i] < 0:
                    signals.append(Signal(Signal.SELL, min(0.5 + abs(histogram[i]) * 2, 1.0), "MACD 柱狀翻負 (空頭訊號)", i))
        return signals


class BollingerStrategy:
    """Bollinger Band breakout/bounce."""

    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std
        self.name = f"Bollinger({period}, {num_std}σ)"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        upper, middle, lower = bollinger_bands(closes, self.period, self.num_std)
        signals = []
        for i in range(1, len(closes)):
            if all(v is not None for v in [upper[i], lower[i], middle[i], upper[i-1], lower[i-1]]):
                if closes[i - 1] <= lower[i - 1] and closes[i] > lower[i]:
                    width = (upper[i] - lower[i]) / middle[i]
                    signals.append(Signal(Signal.BUY, min(0.5 + width, 1.0), f"布林帶下軌反彈 (價格突破下軌)", i))
                elif closes[i - 1] >= upper[i - 1] and closes[i] < upper[i]:
                    width = (upper[i] - lower[i]) / middle[i]
                    signals.append(Signal(Signal.SELL, min(0.5 + width, 1.0), f"布林帶上軌回落 (價格跌破上軌)", i))
        return signals


class KDJStrategy:
    """KDJ golden cross / death cross."""

    def __init__(self, n: int = 9, m1: int = 3, m2: int = 3):
        self.n = n
        self.m1 = m1
        self.m2 = m2
        self.name = f"KDJ({n},{m1},{m2})"

    def generate_signals(self, closes: List[float], highs: List[float] = None, lows: List[float] = None) -> List[Signal]:
        if highs is None:
            highs = closes
        if lows is None:
            lows = closes
        k_line, d_line, j_line = kdj(highs, lows, closes, self.n, self.m1, self.m2)
        signals = []
        for i in range(1, len(closes)):
            if all(v is not None for v in [k_line[i], d_line[i], k_line[i-1], d_line[i-1], j_line[i]]):
                if k_line[i-1] <= d_line[i-1] and k_line[i] > d_line[i] and j_line[i] < 30:
                    signals.append(Signal(Signal.BUY, 0.75, f"KDJ 金叉 (J={j_line[i]:.1f})", i))
                elif k_line[i-1] >= d_line[i-1] and k_line[i] < d_line[i] and j_line[i] > 70:
                    signals.append(Signal(Signal.SELL, 0.75, f"KDJ 死叉 (J={j_line[i]:.1f})", i))
        return signals


class CompositeStrategy:
    """Combines multiple strategies with weighted voting."""

    def __init__(self, weights: Dict[str, float] = None):
        self.strategies = [
            GoldenCrossStrategy(),
            RSIStrategy(),
            MACDStrategy(),
            BollingerStrategy(),
        ]
        self.weights = weights or {s.name: 1.0 for s in self.strategies}
        self.name = "綜合策略 (加權投票)"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        all_signals: Dict[int, Dict[str, List[Signal]]] = {}
        for strategy in self.strategies:
            for sig in strategy.generate_signals(closes):
                if sig.index not in all_signals:
                    all_signals[sig.index] = {"BUY": [], "SELL": []}
                all_signals[sig.index][sig.action].append(sig)

        signals = []
        for idx in sorted(all_signals.keys()):
            buy_score = sum(s.strength * self.weights.get(strat.name, 1.0)
                           for strat in self.strategies
                           for s in all_signals[idx]["BUY"]
                           if any(s in all_signals[idx]["BUY"] for _ in [1]))
            sell_score = sum(s.strength for s in all_signals[idx]["SELL"])

            buy_count = len(all_signals[idx]["BUY"])
            sell_count = len(all_signals[idx]["SELL"])

            if buy_count >= 2 and buy_score > sell_score:
                reasons = " + ".join(s.reason for s in all_signals[idx]["BUY"])
                signals.append(Signal(Signal.BUY, min(buy_score / len(self.strategies), 1.0),
                                      f"[{buy_count}策略共振] {reasons}", idx))
            elif sell_count >= 2 and sell_score > buy_score:
                reasons = " + ".join(s.reason for s in all_signals[idx]["SELL"])
                signals.append(Signal(Signal.SELL, min(sell_score / len(self.strategies), 1.0),
                                      f"[{sell_count}策略共振] {reasons}", idx))
        return signals


STRATEGIES = {
    "golden_cross": GoldenCrossStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
    "kdj": KDJStrategy,
    "composite": CompositeStrategy,
}
