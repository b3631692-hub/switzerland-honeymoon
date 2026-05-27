"""Backtesting engine for strategy evaluation.

Supports: trailing stop, pyramiding, short selling, transaction costs,
dynamic position sizing (fixed, kelly, atr).
"""
import math
from typing import List, Dict, Any
from .strategies import Signal
from .indicators import atr as calc_atr


class Trade:
    def __init__(self, entry_idx: int, entry_price: float, shares: float, direction: str,
                 stop_loss_price: float | None = None, take_profit_price: float | None = None):
        self.entry_idx = entry_idx
        self.entry_price = entry_price
        self.shares = shares
        self.direction = direction
        self.exit_idx: int | None = None
        self.exit_price: float | None = None
        self.pnl: float = 0.0
        self.pnl_pct: float = 0.0
        self.exit_reason: str = ""
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.trailing_high: float | None = None

    def close(self, exit_idx: int, exit_price: float, reason: str = "signal"):
        self.exit_idx = exit_idx
        self.exit_price = exit_price
        self.exit_reason = reason
        if self.direction == "LONG":
            self.pnl = (exit_price - self.entry_price) * self.shares
            self.pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.shares
            self.pnl_pct = (self.entry_price - exit_price) / self.entry_price * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_idx": self.entry_idx,
            "entry_price": round(self.entry_price, 2),
            "exit_idx": self.exit_idx,
            "exit_price": round(self.exit_price, 2) if self.exit_price else None,
            "shares": round(self.shares, 4),
            "direction": self.direction,
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "exit_reason": self.exit_reason,
            "stop_loss_price": round(self.stop_loss_price, 2) if self.stop_loss_price else None,
            "take_profit_price": round(self.take_profit_price, 2) if self.take_profit_price else None,
            "trailing_high": round(self.trailing_high, 2) if self.trailing_high else None,
        }


class BacktestResult:
    def __init__(self):
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.trailing_stop_history: List[float | None] = []
        self.initial_capital: float = 0
        self.final_capital: float = 0
        self.total_return_pct: float = 0
        self.annualized_return: float = 0
        self.sharpe_ratio: float = 0
        self.sortino_ratio: float = 0
        self.calmar_ratio: float = 0
        self.max_drawdown: float = 0
        self.max_drawdown_pct: float = 0
        self.win_rate: float = 0
        self.profit_factor: float = 0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.avg_win: float = 0
        self.avg_loss: float = 0
        self.avg_holding_days: float = 0
        self.expectancy: float = 0
        self.long_trades: int = 0
        self.short_trades: int = 0
        self.long_pnl: float = 0
        self.short_pnl: float = 0
        self.consecutive_wins: int = 0
        self.consecutive_losses: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return": round(self.annualized_return, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "calmar_ratio": round(self.calmar_ratio, 3),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 3),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "expectancy": round(self.expectancy, 2),
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_pnl": round(self.long_pnl, 2),
            "short_pnl": round(self.short_pnl, 2),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "equity_curve": [round(e, 2) for e in self.equity_curve],
            "trailing_stop_history": self.trailing_stop_history,
            "trades": [t.to_dict() for t in self.trades],
        }


class Backtester:
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.001425,
        tax_rate: float = 0.003,
        slippage: float = 0.001,
        position_size: float = 0.95,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        trailing_stop_pct: float | None = None,
        max_positions: int = 1,
        allow_short: bool = False,
        sizing_mode: str = "fixed",
        kelly_lookback: int = 20,
        atr_risk_pct: float = 0.02,
        atr_stop_multiplier: float = 2.0,
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.slippage = slippage
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop_pct = trailing_stop_pct
        self.max_positions = max(1, max_positions)
        self.allow_short = allow_short
        self.sizing_mode = sizing_mode  # "fixed", "kelly", "atr"
        self.kelly_lookback = kelly_lookback
        self.atr_risk_pct = atr_risk_pct
        self.atr_stop_multiplier = atr_stop_multiplier

    def _close_position(self, pos: Trade, idx: int, price: float, reason: str,
                        capital: float, result: BacktestResult) -> float:
        if pos.direction == "LONG":
            sell_price = price * (1 - self.slippage)
            cost = sell_price * pos.shares * (self.commission_rate + self.tax_rate)
            pos.close(idx, sell_price, reason)
            capital += sell_price * pos.shares - cost
        else:
            buy_price = price * (1 + self.slippage)
            cost = buy_price * pos.shares * (self.commission_rate + self.tax_rate)
            pos.close(idx, buy_price, reason)
            capital += (2 * pos.entry_price - buy_price) * pos.shares - cost
        result.trades.append(pos)
        return capital

    def _calc_kelly_fraction(self, closed_trades: List[Trade]) -> float:
        """Calculate Kelly fraction from the last N closed trades."""
        recent = closed_trades[-self.kelly_lookback:] if len(closed_trades) >= self.kelly_lookback else closed_trades
        if len(recent) < 2:
            return self.position_size
        wins = [t for t in recent if t.pnl > 0]
        losses = [t for t in recent if t.pnl <= 0]
        if not wins or not losses:
            return self.position_size
        win_rate = len(wins) / len(recent)
        avg_win = sum(abs(t.pnl_pct) for t in wins) / len(wins)
        avg_loss = sum(abs(t.pnl_pct) for t in losses) / len(losses)
        if avg_loss == 0:
            return self.position_size
        b = avg_win / avg_loss
        kelly = (b * win_rate - (1 - win_rate)) / b
        # Half-Kelly for safety, clamped to [0.05, position_size]
        half_kelly = kelly * 0.5
        return max(0.05, min(half_kelly, self.position_size))

    def _calc_atr_shares(self, capital: float, price: float, atr_value: float) -> float:
        """Calculate position size based on ATR: risk atr_risk_pct of capital, stop = atr_stop_multiplier * ATR."""
        if atr_value <= 0:
            return 0
        risk_amount = capital * self.atr_risk_pct
        stop_distance = atr_value * self.atr_stop_multiplier
        shares = risk_amount / stop_distance
        max_shares = (capital * self.position_size) / price
        return min(shares, max_shares)

    def run(self, closes: List[float], signals: List[Signal], dates: List[str] = None,
            highs: List[float] = None, lows: List[float] = None) -> BacktestResult:
        result = BacktestResult()
        result.initial_capital = self.initial_capital

        capital = self.initial_capital
        positions: List[Trade] = []
        high_watermarks: Dict[int, float] = {}
        equity_curve: List[float] = []
        ts_history: List[float | None] = []

        # Pre-compute ATR values if needed for ATR sizing
        atr_values: List[float | None] = [None] * len(closes)
        if self.sizing_mode == "atr":
            if highs is not None and lows is not None:
                atr_values = calc_atr(highs, lows, closes, 14)
            else:
                # Fallback: use closes as proxy for highs/lows
                atr_values = calc_atr(closes, closes, closes, 14)

        # Track closed trades for Kelly sizing
        closed_trades: List[Trade] = []

        signal_map: Dict[int, Signal] = {}
        for sig in signals:
            if sig.index not in signal_map or sig.strength > signal_map[sig.index].strength:
                signal_map[sig.index] = sig

        for i in range(len(closes)):
            price = closes[i]

            # --- 1. Update high watermarks & check trailing stops ---
            if self.trailing_stop_pct and positions:
                to_close = []
                for pos in positions:
                    pid = id(pos)
                    if pos.direction == "LONG":
                        hwm = max(high_watermarks.get(pid, pos.entry_price), price)
                        high_watermarks[pid] = hwm
                        ts_level = hwm * (1 - self.trailing_stop_pct)
                        if price <= ts_level:
                            pos.trailing_high = hwm
                            to_close.append((pos, "trailing_stop"))
                    else:
                        lwm = min(high_watermarks.get(pid, pos.entry_price), price)
                        high_watermarks[pid] = lwm
                        ts_level = lwm * (1 + self.trailing_stop_pct)
                        if price >= ts_level:
                            pos.trailing_high = lwm
                            to_close.append((pos, "trailing_stop"))
                for pos, reason in to_close:
                    capital = self._close_position(pos, i, price, reason, capital, result)
                    closed_trades.append(result.trades[-1])
                    if id(pos) in high_watermarks:
                        del high_watermarks[id(pos)]
                    positions.remove(pos)

            # --- 2. Check fixed stop-loss ---
            if self.stop_loss and positions:
                to_close = []
                for pos in positions:
                    if pos.direction == "LONG":
                        loss_pct = (pos.entry_price - price) / pos.entry_price
                        if loss_pct >= self.stop_loss:
                            to_close.append(pos)
                    else:
                        loss_pct = (price - pos.entry_price) / pos.entry_price
                        if loss_pct >= self.stop_loss:
                            to_close.append(pos)
                for pos in to_close:
                    capital = self._close_position(pos, i, price, "stop_loss", capital, result)
                    closed_trades.append(result.trades[-1])
                    high_watermarks.pop(id(pos), None)
                    positions.remove(pos)

            # --- 3. Check take-profit ---
            if self.take_profit and positions:
                to_close = []
                for pos in positions:
                    if pos.direction == "LONG":
                        gain_pct = (price - pos.entry_price) / pos.entry_price
                        if gain_pct >= self.take_profit:
                            to_close.append(pos)
                    else:
                        gain_pct = (pos.entry_price - price) / pos.entry_price
                        if gain_pct >= self.take_profit:
                            to_close.append(pos)
                for pos in to_close:
                    capital = self._close_position(pos, i, price, "take_profit", capital, result)
                    closed_trades.append(result.trades[-1])
                    high_watermarks.pop(id(pos), None)
                    positions.remove(pos)

            # --- 4. Process signals ---
            if i in signal_map:
                sig = signal_map[i]
                longs = [p for p in positions if p.direction == "LONG"]
                shorts = [p for p in positions if p.direction == "SHORT"]

                if sig.action == Signal.BUY:
                    for pos in shorts:
                        capital = self._close_position(pos, i, price, "signal", capital, result)
                        closed_trades.append(result.trades[-1])
                        high_watermarks.pop(id(pos), None)
                    positions = [p for p in positions if p.direction == "LONG"]

                    if len(longs) < self.max_positions:
                        buy_price = price * (1 + self.slippage)

                        # --- Dynamic position sizing ---
                        if self.sizing_mode == "kelly" and closed_trades:
                            kelly_frac = self._calc_kelly_fraction(closed_trades)
                            alloc = kelly_frac / self.max_positions
                            available = capital * alloc
                            cost = available * self.commission_rate
                            shares = (available - cost) / buy_price
                        elif self.sizing_mode == "atr" and atr_values[i] is not None:
                            shares = self._calc_atr_shares(capital, buy_price, atr_values[i])
                            cost = buy_price * shares * self.commission_rate
                        else:
                            alloc = self.position_size / self.max_positions
                            available = capital * alloc
                            cost = available * self.commission_rate
                            shares = (available - cost) / buy_price

                        if shares > 0 and capital > buy_price * shares + cost:
                            sl_p = buy_price * (1 - self.stop_loss) if self.stop_loss else None
                            tp_p = buy_price * (1 + self.take_profit) if self.take_profit else None
                            # For ATR sizing, set stop based on ATR if no explicit stop_loss
                            if self.sizing_mode == "atr" and sl_p is None and atr_values[i] is not None:
                                sl_p = buy_price - atr_values[i] * self.atr_stop_multiplier
                            new_pos = Trade(i, buy_price, shares, "LONG", sl_p, tp_p)
                            capital -= buy_price * shares + cost
                            positions.append(new_pos)
                            high_watermarks[id(new_pos)] = buy_price

                elif sig.action == Signal.SELL:
                    for pos in longs:
                        capital = self._close_position(pos, i, price, "signal", capital, result)
                        closed_trades.append(result.trades[-1])
                        high_watermarks.pop(id(pos), None)
                    positions = [p for p in positions if p.direction == "SHORT"]

                    if self.allow_short and len(shorts) < self.max_positions:
                        sell_price = price * (1 - self.slippage)

                        # --- Dynamic position sizing ---
                        if self.sizing_mode == "kelly" and closed_trades:
                            kelly_frac = self._calc_kelly_fraction(closed_trades)
                            alloc = kelly_frac / self.max_positions
                            available = capital * alloc
                            cost = available * self.commission_rate
                            shares = (available - cost) / sell_price
                        elif self.sizing_mode == "atr" and atr_values[i] is not None:
                            shares = self._calc_atr_shares(capital, sell_price, atr_values[i])
                            cost = sell_price * shares * self.commission_rate
                        else:
                            alloc = self.position_size / self.max_positions
                            available = capital * alloc
                            cost = available * self.commission_rate
                            shares = (available - cost) / sell_price

                        if shares > 0:
                            sl_p = sell_price * (1 + self.stop_loss) if self.stop_loss else None
                            tp_p = sell_price * (1 - self.take_profit) if self.take_profit else None
                            # For ATR sizing, set stop based on ATR if no explicit stop_loss
                            if self.sizing_mode == "atr" and sl_p is None and atr_values[i] is not None:
                                sl_p = sell_price + atr_values[i] * self.atr_stop_multiplier
                            new_pos = Trade(i, sell_price, shares, "SHORT", sl_p, tp_p)
                            capital += sell_price * shares - cost
                            positions.append(new_pos)
                            high_watermarks[id(new_pos)] = sell_price

            # --- 5. Mark to market ---
            mark_value = capital
            for pos in positions:
                if pos.direction == "LONG":
                    mark_value += pos.shares * price
                else:
                    mark_value += pos.shares * (2 * pos.entry_price - price)
            equity_curve.append(mark_value)

            # --- 6. Trailing stop history ---
            if positions and self.trailing_stop_pct:
                pos = positions[0]
                pid = id(pos)
                hwm = high_watermarks.get(pid, pos.entry_price)
                if pos.direction == "LONG":
                    ts_history.append(round(hwm * (1 - self.trailing_stop_pct), 2))
                else:
                    ts_history.append(round(hwm * (1 + self.trailing_stop_pct), 2))
            else:
                ts_history.append(None)

        # --- Close remaining positions ---
        for pos in positions:
            capital = self._close_position(pos, len(closes) - 1, closes[-1], "end_of_data", capital, result)
        if equity_curve:
            equity_curve[-1] = capital

        result.equity_curve = equity_curve
        result.trailing_stop_history = ts_history
        result.final_capital = capital
        result.total_return_pct = (capital - self.initial_capital) / self.initial_capital * 100

        trading_days = len(closes)
        years = trading_days / 252
        if years > 0 and capital > 0:
            result.annualized_return = ((capital / self.initial_capital) ** (1 / years) - 1) * 100

        self._calc_metrics(result, equity_curve)
        return result

    def _calc_metrics(self, result: BacktestResult, equity_curve: List[float]):
        if len(equity_curve) < 2:
            return

        daily_returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i - 1] != 0:
                daily_returns.append((equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1])

        if daily_returns:
            avg_ret = sum(daily_returns) / len(daily_returns)
            if len(daily_returns) > 1:
                variance = sum((r - avg_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
                std_ret = math.sqrt(variance)
                if std_ret > 0:
                    result.sharpe_ratio = (avg_ret / std_ret) * math.sqrt(252)

            downside = [r for r in daily_returns if r < 0]
            if downside:
                down_var = sum(r ** 2 for r in downside) / len(downside)
                down_std = math.sqrt(down_var)
                if down_std > 0:
                    result.sortino_ratio = (avg_ret / down_std) * math.sqrt(252)

        peak = equity_curve[0]
        max_dd = 0
        max_dd_pct = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = dd / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
        result.max_drawdown = max_dd
        result.max_drawdown_pct = max_dd_pct * 100

        if result.max_drawdown_pct > 0:
            result.calmar_ratio = result.annualized_return / result.max_drawdown_pct

        wins = [t for t in result.trades if t.pnl > 0]
        losses = [t for t in result.trades if t.pnl <= 0]
        result.total_trades = len(result.trades)
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)

        if result.total_trades > 0:
            result.win_rate = len(wins) / result.total_trades * 100

        total_profit = sum(t.pnl for t in wins)
        total_loss = abs(sum(t.pnl for t in losses))
        if total_loss > 0:
            result.profit_factor = total_profit / total_loss

        if wins:
            result.avg_win = sum(t.pnl_pct for t in wins) / len(wins)
        if losses:
            result.avg_loss = sum(t.pnl_pct for t in losses) / len(losses)

        if result.total_trades > 0:
            holding_periods = [t.exit_idx - t.entry_idx for t in result.trades if t.exit_idx is not None]
            if holding_periods:
                result.avg_holding_days = sum(holding_periods) / len(holding_periods)
            result.expectancy = sum(t.pnl for t in result.trades) / result.total_trades

        longs = [t for t in result.trades if t.direction == "LONG"]
        shorts = [t for t in result.trades if t.direction == "SHORT"]
        result.long_trades = len(longs)
        result.short_trades = len(shorts)
        result.long_pnl = sum(t.pnl for t in longs)
        result.short_pnl = sum(t.pnl for t in shorts)

        max_cw = 0
        max_cl = 0
        cw = 0
        cl = 0
        for t in result.trades:
            if t.pnl > 0:
                cw += 1
                cl = 0
            else:
                cl += 1
                cw = 0
            max_cw = max(max_cw, cw)
            max_cl = max(max_cl, cl)
        result.consecutive_wins = max_cw
        result.consecutive_losses = max_cl
