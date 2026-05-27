"""Backtesting engine for strategy evaluation."""
import math
from typing import List, Dict, Any
from .strategies import Signal


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
        }


class BacktestResult:
    def __init__(self):
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.initial_capital: float = 0
        self.final_capital: float = 0
        self.total_return_pct: float = 0
        self.annualized_return: float = 0
        self.sharpe_ratio: float = 0
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return": round(self.annualized_return, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
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
            "equity_curve": [round(e, 2) for e in self.equity_curve],
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
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.slippage = slippage
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def run(self, closes: List[float], signals: List[Signal], dates: List[str] = None) -> BacktestResult:
        result = BacktestResult()
        result.initial_capital = self.initial_capital

        capital = self.initial_capital
        position: Trade | None = None
        equity_curve = []

        signal_map: Dict[int, Signal] = {}
        for sig in signals:
            if sig.index not in signal_map or sig.strength > signal_map[sig.index].strength:
                signal_map[sig.index] = sig

        for i in range(len(closes)):
            price = closes[i]

            if position and self.stop_loss:
                if position.direction == "LONG":
                    loss_pct = (position.entry_price - price) / position.entry_price
                    if loss_pct >= self.stop_loss:
                        sell_price = price * (1 - self.slippage)
                        cost = sell_price * position.shares * (self.commission_rate + self.tax_rate)
                        position.close(i, sell_price, "stop_loss")
                        capital += sell_price * position.shares - cost
                        result.trades.append(position)
                        position = None

            if position and self.take_profit:
                if position.direction == "LONG":
                    gain_pct = (price - position.entry_price) / position.entry_price
                    if gain_pct >= self.take_profit:
                        sell_price = price * (1 - self.slippage)
                        cost = sell_price * position.shares * (self.commission_rate + self.tax_rate)
                        position.close(i, sell_price, "take_profit")
                        capital += sell_price * position.shares - cost
                        result.trades.append(position)
                        position = None

            if i in signal_map:
                sig = signal_map[i]

                if sig.action == Signal.BUY and position is None:
                    buy_price = price * (1 + self.slippage)
                    available = capital * self.position_size
                    cost = available * self.commission_rate
                    shares = (available - cost) / buy_price
                    if shares > 0:
                        sl_price = buy_price * (1 - self.stop_loss) if self.stop_loss else None
                        tp_price = buy_price * (1 + self.take_profit) if self.take_profit else None
                        position = Trade(i, buy_price, shares, "LONG", sl_price, tp_price)
                        capital -= buy_price * shares + cost

                elif sig.action == Signal.SELL and position is not None:
                    sell_price = price * (1 - self.slippage)
                    cost = sell_price * position.shares * (self.commission_rate + self.tax_rate)
                    position.close(i, sell_price, "signal")
                    capital += sell_price * position.shares - cost
                    result.trades.append(position)
                    position = None

            if position:
                mark_value = capital + position.shares * price
            else:
                mark_value = capital
            equity_curve.append(mark_value)

        if position:
            sell_price = closes[-1] * (1 - self.slippage)
            cost = sell_price * position.shares * (self.commission_rate + self.tax_rate)
            position.close(len(closes) - 1, sell_price, "end_of_data")
            capital += sell_price * position.shares - cost
            result.trades.append(position)
            equity_curve[-1] = capital

        result.equity_curve = equity_curve
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
