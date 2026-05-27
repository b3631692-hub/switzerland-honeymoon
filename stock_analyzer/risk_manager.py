"""Risk management and position sizing."""
import math
from typing import List, Dict, Any


class RiskManager:
    def __init__(
        self,
        max_position_pct: float = 0.25,
        max_portfolio_risk: float = 0.02,
        max_drawdown_limit: float = 0.15,
        max_correlated_positions: int = 3,
    ):
        self.max_position_pct = max_position_pct
        self.max_portfolio_risk = max_portfolio_risk
        self.max_drawdown_limit = max_drawdown_limit
        self.max_correlated_positions = max_correlated_positions

    def kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        if avg_loss == 0 or win_rate <= 0:
            return 0
        b = abs(avg_win / avg_loss)
        p = win_rate
        q = 1 - p
        kelly = (b * p - q) / b
        return max(min(kelly * 0.5, self.max_position_pct), 0)

    def fixed_fraction(self, capital: float, risk_per_trade: float, entry_price: float, stop_price: float) -> float:
        risk_amount = capital * risk_per_trade
        price_risk = abs(entry_price - stop_price)
        if price_risk == 0:
            return 0
        shares = risk_amount / price_risk
        max_shares = (capital * self.max_position_pct) / entry_price
        return min(shares, max_shares)

    def position_size_atr(self, capital: float, atr_value: float, entry_price: float, risk_multiplier: float = 2.0) -> float:
        if atr_value <= 0:
            return 0
        risk_amount = capital * self.max_portfolio_risk
        stop_distance = atr_value * risk_multiplier
        shares = risk_amount / stop_distance
        max_shares = (capital * self.max_position_pct) / entry_price
        return min(shares, max_shares)

    def check_drawdown(self, equity_curve: List[float]) -> Dict[str, Any]:
        if not equity_curve:
            return {"ok": True, "current_dd": 0, "max_dd": 0}
        peak = equity_curve[0]
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd_pct = (peak - eq) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd_pct)
        current_dd = (peak - equity_curve[-1]) / peak if peak > 0 else 0
        breached = max_dd >= self.max_drawdown_limit
        return {
            "ok": not breached,
            "current_drawdown_pct": round(current_dd * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "limit_pct": self.max_drawdown_limit * 100,
            "breached": breached,
            "action": "停止交易！最大回撤已超過限制" if breached else "正常",
        }

    def risk_reward_ratio(self, entry: float, stop: float, target: float) -> float:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk == 0:
            return 0
        return reward / risk

    def calculate_var(self, returns: List[float], confidence: float = 0.95, capital: float = 1_000_000) -> float:
        if not returns:
            return 0
        sorted_returns = sorted(returns)
        idx = int(len(sorted_returns) * (1 - confidence))
        var_pct = sorted_returns[idx]
        return abs(var_pct * capital)

    def score_trade(self, win_rate: float, risk_reward: float, signal_strength: float) -> Dict[str, Any]:
        rr_score = min(risk_reward / 3.0, 1.0) * 40
        wr_score = win_rate * 30
        sig_score = signal_strength * 30
        total = rr_score + wr_score + sig_score
        if total >= 75:
            grade = "A"
            action = "強烈建議進場"
        elif total >= 60:
            grade = "B"
            action = "可以考慮進場"
        elif total >= 45:
            grade = "C"
            action = "觀望為主"
        else:
            grade = "D"
            action = "不建議進場"
        return {
            "total_score": round(total, 1),
            "grade": grade,
            "action": action,
            "breakdown": {
                "risk_reward_score": round(rr_score, 1),
                "win_rate_score": round(wr_score, 1),
                "signal_score": round(sig_score, 1),
            }
        }
