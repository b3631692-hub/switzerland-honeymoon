"""Trading strategies with buy/sell signal generation."""
from typing import List, Dict, Any
from .indicators import sma, ema, rsi, macd, bollinger_bands, kdj, atr, support_resistance


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


class EMACrossStrategy:
    """EMA crossover with EMA200 trend filter.

    Buy when short EMA crosses above long EMA AND price > EMA200.
    Sell when short EMA crosses below long EMA AND price < EMA200.
    """

    def __init__(self, short_period: int = 12, long_period: int = 26, trend_period: int = 200):
        self.short_period = short_period
        self.long_period = long_period
        self.trend_period = trend_period
        self.name = f"EMA CrossOver({short_period}/{long_period}) Trend({trend_period})"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        short_ema = ema(closes, self.short_period)
        long_ema = ema(closes, self.long_period)
        trend_ema = ema(closes, self.trend_period)
        signals = []
        for i in range(1, len(closes)):
            if all(v is not None for v in [short_ema[i], long_ema[i], short_ema[i - 1], long_ema[i - 1]]):
                # Bullish crossover: short EMA crosses above long EMA
                if short_ema[i - 1] <= long_ema[i - 1] and short_ema[i] > long_ema[i]:
                    # Trend filter: only take longs when price > EMA200
                    if trend_ema[i] is None or closes[i] > trend_ema[i]:
                        gap = (short_ema[i] - long_ema[i]) / long_ema[i]
                        signals.append(Signal(
                            Signal.BUY, min(0.5 + gap * 20, 1.0),
                            f"EMA金叉 EMA{self.short_period}↑EMA{self.long_period} (趨勢濾網通過)", i
                        ))
                # Bearish crossover: short EMA crosses below long EMA
                elif short_ema[i - 1] >= long_ema[i - 1] and short_ema[i] < long_ema[i]:
                    # Trend filter: only take shorts when price < EMA200
                    if trend_ema[i] is None or closes[i] < trend_ema[i]:
                        gap = (long_ema[i] - short_ema[i]) / long_ema[i]
                        signals.append(Signal(
                            Signal.SELL, min(0.5 + gap * 20, 1.0),
                            f"EMA死叉 EMA{self.short_period}↓EMA{self.long_period} (趨勢濾網通過)", i
                        ))
        return signals


class VolumeBreakoutStrategy:
    """Volume breakout strategy with divergence detection.

    Buy when volume > 2x average volume AND price closes above 20-day high.
    Sell when volume > 2x average volume AND price closes below 20-day low.
    Also generates sell warnings on volume-price divergence (price up + volume down).
    """

    def __init__(self, vol_multiplier: float = 2.0, lookback: int = 20):
        self.vol_multiplier = vol_multiplier
        self.lookback = lookback
        self.name = f"Volume Breakout({lookback}d, {vol_multiplier}x)"

    def generate_signals(self, closes: List[float], volumes: List[float] = None,
                         highs: List[float] = None, lows: List[float] = None) -> List[Signal]:
        if volumes is None:
            # Cannot operate without volume data; return empty
            return []
        if highs is None:
            highs = closes
        if lows is None:
            lows = closes

        signals = []
        n = len(closes)
        for i in range(self.lookback, n):
            # Average volume over lookback window (excluding current bar)
            avg_vol = sum(volumes[i - self.lookback:i]) / self.lookback
            if avg_vol <= 0:
                continue

            vol_ratio = volumes[i] / avg_vol
            high_volume = vol_ratio >= self.vol_multiplier

            # 20-day high/low (excluding current bar)
            period_high = max(highs[i - self.lookback:i])
            period_low = min(lows[i - self.lookback:i])

            # Buy: high volume + price closes above 20-day high
            if high_volume and closes[i] > period_high:
                strength = min(0.5 + (vol_ratio - self.vol_multiplier) * 0.15, 1.0)
                signals.append(Signal(
                    Signal.BUY, strength,
                    f"量價突破 成交量{vol_ratio:.1f}x + 突破{self.lookback}日高點", i
                ))

            # Sell: high volume + price closes below 20-day low
            elif high_volume and closes[i] < period_low:
                strength = min(0.5 + (vol_ratio - self.vol_multiplier) * 0.15, 1.0)
                signals.append(Signal(
                    Signal.SELL, strength,
                    f"量價崩跌 成交量{vol_ratio:.1f}x + 跌破{self.lookback}日低點", i
                ))

            # Volume-price divergence: price up but volume declining
            elif i >= self.lookback + 5:
                price_up = closes[i] > closes[i - 5]
                recent_avg_vol = sum(volumes[i - 5:i]) / 5
                prev_avg_vol = sum(volumes[i - 10:i - 5]) / 5 if i >= self.lookback + 10 else avg_vol
                vol_declining = recent_avg_vol < prev_avg_vol * 0.8 if prev_avg_vol > 0 else False
                if price_up and vol_declining:
                    signals.append(Signal(
                        Signal.SELL, 0.4,
                        f"量價背離警告 價格上漲但成交量萎縮", i
                    ))

        return signals


class RiskRewardFilter:
    """Wraps any strategy and filters signals by risk/reward ratio.

    For BUY signals: only keep if potential reward (nearest resistance - price)
    divided by risk (ATR * multiplier) >= min_rr.
    For SELL signals: similar logic using nearest support.
    """

    def __init__(self, strategy=None, min_rr: float = 2.0, atr_period: int = 14):
        if strategy is None:
            strategy = CompositeStrategy()
        self.strategy = strategy
        self.min_rr = min_rr
        self.atr_period = atr_period
        self.name = f"風險報酬過濾 (RR≥{min_rr}) {strategy.name}"

    def generate_signals(self, closes: List[float]) -> List[Signal]:
        raw_signals = self.strategy.generate_signals(closes)
        if len(closes) < self.atr_period + 2:
            return raw_signals

        # Compute ATR using closes as proxy for highs/lows
        highs = closes
        lows = closes
        atr_values = atr(highs, lows, closes, self.atr_period)

        # Compute support/resistance levels
        sr_window = min(20, len(closes) // 4) if len(closes) > 8 else 2
        if sr_window < 2:
            return raw_signals
        supports, resistances = support_resistance(closes, sr_window)

        filtered = []
        for sig in raw_signals:
            idx = sig.index
            current_atr = atr_values[idx] if idx < len(atr_values) and atr_values[idx] is not None else None
            if current_atr is None or current_atr <= 0:
                # Cannot compute RR, keep signal as-is
                filtered.append(sig)
                continue

            price = closes[idx]
            risk = current_atr

            if sig.action == Signal.BUY:
                # Find nearest resistance above price
                above = [r for r in resistances if r > price]
                if above:
                    target = min(above)
                    reward = target - price
                else:
                    # No resistance found; estimate reward as 3*ATR
                    reward = current_atr * 3

                rr = reward / risk if risk > 0 else 0
                if rr >= self.min_rr:
                    filtered.append(sig)

            elif sig.action == Signal.SELL:
                # Find nearest support below price
                below = [s for s in supports if s < price]
                if below:
                    target = max(below)
                    reward = price - target
                else:
                    reward = current_atr * 3

                rr = reward / risk if risk > 0 else 0
                if rr >= self.min_rr:
                    filtered.append(sig)
            else:
                filtered.append(sig)

        return filtered


STRATEGIES = {
    "golden_cross": GoldenCrossStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
    "kdj": KDJStrategy,
    "composite": CompositeStrategy,
    "ema_cross": EMACrossStrategy,
    "volume_breakout": VolumeBreakoutStrategy,
    "rr_filtered": RiskRewardFilter,
}
