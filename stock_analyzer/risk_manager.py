"""Risk management and position sizing."""
import math
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .backtester import BacktestResult


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


class StrategyScorer:
    """Grades a BacktestResult on an A-F scale based on multiple metrics.

    Scoring weights:
      - Sharpe ratio:   25%
      - Profit factor:  20%
      - Win rate:       20%
      - Max drawdown:   20%
      - Consistency:    15%  (1 - coefficient of variation of monthly returns)

    Grade scale: A >= 80, B >= 65, C >= 50, D >= 35, F < 35
    """

    def score(self, result: "BacktestResult") -> Dict[str, Any]:
        from .backtester import BacktestResult

        # --- Sharpe score (25%) ---
        # Map sharpe: <=0 -> 0, >=3 -> 100
        raw_sharpe = result.sharpe_ratio
        sharpe_pct = max(0.0, min(raw_sharpe / 3.0, 1.0)) * 100

        # --- Profit factor score (20%) ---
        # Map PF: <=0.5 -> 0, >=3 -> 100
        raw_pf = result.profit_factor
        pf_pct = max(0.0, min((raw_pf - 0.5) / 2.5, 1.0)) * 100

        # --- Win rate score (20%) ---
        # Map win_rate: 0% -> 0, 100% -> 100 (it's already a percentage)
        raw_wr = result.win_rate  # already 0-100
        wr_pct = max(0.0, min(raw_wr, 100.0))

        # --- Max drawdown score (20%) ---
        # Lower is better: 0% dd -> 100, >=50% dd -> 0
        raw_dd = result.max_drawdown_pct
        dd_pct = max(0.0, min((50.0 - raw_dd) / 50.0, 1.0)) * 100

        # --- Consistency score (15%) ---
        consistency_pct = self._calc_consistency(result.equity_curve)

        # Weighted total
        total_score = (
            sharpe_pct * 0.25
            + pf_pct * 0.20
            + wr_pct * 0.20
            + dd_pct * 0.20
            + consistency_pct * 0.15
        )
        total_score = max(0.0, min(total_score, 100.0))

        # Grade
        if total_score >= 80:
            grade = "A"
        elif total_score >= 65:
            grade = "B"
        elif total_score >= 50:
            grade = "C"
        elif total_score >= 35:
            grade = "D"
        else:
            grade = "F"

        # Recommendation in Chinese
        recommendations = {
            "A": "策略表現優異，各項指標均衡，建議持續使用並適度加大部位。",
            "B": "策略表現良好，可投入實盤但需注意風控，建議搭配移動停損。",
            "C": "策略表現中等，建議先用小部位測試或結合其他策略使用。",
            "D": "策略表現偏弱，建議優化參數或更換策略後再行使用。",
            "F": "策略表現不佳，不建議投入實盤，請重新檢視策略邏輯與參數。",
        }

        return {
            "total_score": round(total_score, 1),
            "grade": grade,
            "recommendation": recommendations.get(grade, ""),
            "breakdown": {
                "sharpe": round(sharpe_pct, 1),
                "profit_factor": round(pf_pct, 1),
                "win_rate": round(wr_pct, 1),
                "max_drawdown": round(dd_pct, 1),
                "consistency": round(consistency_pct, 1),
            },
        }

    def _calc_consistency(self, equity_curve: List[float]) -> float:
        """Consistency = (1 - CV of monthly returns) * 100, clamped to [0, 100].

        Monthly returns are approximated by splitting the equity curve into
        ~21-day segments (trading days per month).
        """
        if not equity_curve or len(equity_curve) < 42:
            return 50.0  # not enough data, neutral score

        month_len = 21
        monthly_returns = []
        for i in range(0, len(equity_curve) - month_len, month_len):
            start_val = equity_curve[i]
            end_val = equity_curve[i + month_len]
            if start_val > 0:
                monthly_returns.append((end_val - start_val) / start_val)

        if len(monthly_returns) < 2:
            return 50.0

        mean_ret = sum(monthly_returns) / len(monthly_returns)
        if mean_ret == 0:
            return 50.0

        variance = sum((r - mean_ret) ** 2 for r in monthly_returns) / (len(monthly_returns) - 1)
        std_ret = math.sqrt(variance)
        cv = abs(std_ret / mean_ret)

        # Map: CV 0 -> 100, CV >= 3 -> 0
        consistency = max(0.0, min((3.0 - cv) / 3.0, 1.0)) * 100
        return consistency
