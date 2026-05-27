"""Advanced backtesting algorithms.

- Walk-Forward Analysis: rolling OOS validation
- Monte Carlo Simulation: robustness testing via trade shuffling
- Grid Search Optimizer: exhaustive parameter search
"""
import math
import random
from typing import List, Dict, Any, Tuple
from .strategies import STRATEGIES, Signal
from .backtester import Backtester, BacktestResult, Trade


# ═══════════════════════════════════════════════════════════════
#  Monte Carlo Simulation
# ═══════════════════════════════════════════════════════════════
class MonteCarloSimulator:
    def __init__(self, n_simulations: int = 500, seed: int | None = None):
        self.n_simulations = n_simulations
        self.seed = seed

    def run(self, trades: List[Trade], initial_capital: float) -> Dict[str, Any]:
        if not trades:
            return {"error": "no trades", "simulations": []}

        rng = random.Random(self.seed)
        pnl_list = [t.pnl for t in trades]
        pnl_pct_list = [t.pnl_pct for t in trades]

        final_capitals = []
        max_drawdowns = []
        all_curves = []
        sharpe_ratios = []

        for _ in range(self.n_simulations):
            shuffled_pnl = pnl_list[:]
            rng.shuffle(shuffled_pnl)

            capital = initial_capital
            curve = [capital]
            peak = capital
            max_dd = 0
            returns = []

            for pnl in shuffled_pnl:
                prev = capital
                capital += pnl
                curve.append(capital)
                if capital > peak:
                    peak = capital
                dd_pct = (peak - capital) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd_pct)
                if prev > 0:
                    returns.append((capital - prev) / prev)

            final_capitals.append(capital)
            max_drawdowns.append(max_dd * 100)
            all_curves.append(curve)

            if returns and len(returns) > 1:
                avg_r = sum(returns) / len(returns)
                var = sum((r - avg_r) ** 2 for r in returns) / (len(returns) - 1)
                std_r = math.sqrt(var) if var > 0 else 0
                sr = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0
                sharpe_ratios.append(sr)

        final_capitals.sort()
        max_drawdowns.sort()
        n = len(final_capitals)

        def percentile(arr, p):
            idx = int(len(arr) * p / 100)
            return arr[min(idx, len(arr) - 1)]

        p5_curve = []
        p25_curve = []
        p50_curve = []
        p75_curve = []
        p95_curve = []
        max_len = max(len(c) for c in all_curves)
        for step in range(max_len):
            vals = sorted(c[step] if step < len(c) else c[-1] for c in all_curves)
            p5_curve.append(round(percentile(vals, 5), 2))
            p25_curve.append(round(percentile(vals, 25), 2))
            p50_curve.append(round(percentile(vals, 50), 2))
            p75_curve.append(round(percentile(vals, 75), 2))
            p95_curve.append(round(percentile(vals, 95), 2))

        return {
            "n_simulations": self.n_simulations,
            "n_trades": len(trades),
            "initial_capital": initial_capital,
            "final_capital_stats": {
                "mean": round(sum(final_capitals) / n, 2),
                "median": round(percentile(final_capitals, 50), 2),
                "p5": round(percentile(final_capitals, 5), 2),
                "p25": round(percentile(final_capitals, 25), 2),
                "p75": round(percentile(final_capitals, 75), 2),
                "p95": round(percentile(final_capitals, 95), 2),
                "min": round(min(final_capitals), 2),
                "max": round(max(final_capitals), 2),
                "std": round(math.sqrt(sum((x - sum(final_capitals)/n)**2 for x in final_capitals) / n), 2),
            },
            "max_drawdown_stats": {
                "mean": round(sum(max_drawdowns) / n, 2),
                "median": round(percentile(max_drawdowns, 50), 2),
                "p5": round(percentile(max_drawdowns, 5), 2),
                "p95": round(percentile(max_drawdowns, 95), 2),
                "worst": round(max(max_drawdowns), 2),
            },
            "sharpe_stats": {
                "mean": round(sum(sharpe_ratios) / len(sharpe_ratios), 3) if sharpe_ratios else 0,
                "median": round(percentile(sorted(sharpe_ratios), 50), 3) if sharpe_ratios else 0,
            },
            "probability_of_profit": round(sum(1 for x in final_capitals if x > initial_capital) / n * 100, 1),
            "probability_of_ruin": round(sum(1 for x in final_capitals if x < initial_capital * 0.5) / n * 100, 1),
            "confidence_bands": {
                "p5": p5_curve,
                "p25": p25_curve,
                "p50": p50_curve,
                "p75": p75_curve,
                "p95": p95_curve,
            },
            "histogram": _build_histogram(final_capitals, 30),
        }


def _build_histogram(values: List[float], bins: int = 30) -> Dict[str, Any]:
    if not values:
        return {"edges": [], "counts": []}
    mn, mx = min(values), max(values)
    if mn == mx:
        return {"edges": [mn], "counts": [len(values)]}
    width = (mx - mn) / bins
    edges = [round(mn + i * width, 2) for i in range(bins + 1)]
    counts = [0] * bins
    for v in values:
        idx = min(int((v - mn) / width), bins - 1)
        counts[idx] += 1
    return {"edges": edges, "counts": counts}


# ═══════════════════════════════════════════════════════════════
#  Walk-Forward Analysis
# ═══════════════════════════════════════════════════════════════
class WalkForwardAnalyzer:
    def __init__(self, n_windows: int = 5, train_ratio: float = 0.7):
        self.n_windows = n_windows
        self.train_ratio = train_ratio

    def run(self, closes: List[float], strategy_name: str, capital: float = 1_000_000,
            param_grid: Dict | None = None, **bt_kwargs) -> Dict[str, Any]:
        n = len(closes)
        window_size = n // self.n_windows
        if window_size < 30:
            return {"error": "insufficient data", "windows": []}

        if param_grid is None:
            param_grid = DEFAULT_PARAM_GRIDS.get(strategy_name, {})

        windows = []
        oos_equity = [capital]
        cumulative_capital = capital

        for w in range(self.n_windows):
            start = w * window_size
            end = min(start + window_size, n)
            if end - start < 20:
                continue

            train_end = start + int((end - start) * self.train_ratio)
            train_data = closes[start:train_end]
            test_data = closes[train_end:end]

            if len(train_data) < 15 or len(test_data) < 5:
                continue

            best_params, best_sharpe = self._optimize_window(
                train_data, strategy_name, param_grid, capital, bt_kwargs
            )

            strategy_cls = STRATEGIES.get(strategy_name)
            if not strategy_cls:
                continue
            strategy = strategy_cls(**best_params) if best_params else strategy_cls()
            signals = strategy.generate_signals(test_data)

            bt = Backtester(initial_capital=cumulative_capital, **bt_kwargs)
            result = bt.run(test_data, signals)

            ret_pct = result.total_return_pct
            cumulative_capital = result.final_capital

            for eq in result.equity_curve[1:]:
                oos_equity.append(eq)

            windows.append({
                "window": w + 1,
                "train_period": f"{start}→{train_end}",
                "test_period": f"{train_end}→{end}",
                "train_bars": train_end - start,
                "test_bars": end - train_end,
                "best_params": {k: v for k, v in best_params.items()},
                "train_sharpe": round(best_sharpe, 3),
                "oos_return_pct": round(ret_pct, 2),
                "oos_sharpe": round(result.sharpe_ratio, 3),
                "oos_trades": result.total_trades,
                "oos_win_rate": round(result.win_rate, 1),
                "oos_max_dd": round(result.max_drawdown_pct, 2),
            })

        total_ret = (cumulative_capital - capital) / capital * 100
        avg_oos_ret = sum(w["oos_return_pct"] for w in windows) / len(windows) if windows else 0

        return {
            "n_windows": len(windows),
            "train_ratio": self.train_ratio,
            "initial_capital": capital,
            "final_capital": round(cumulative_capital, 2),
            "total_return_pct": round(total_ret, 2),
            "avg_oos_return": round(avg_oos_ret, 2),
            "oos_equity_curve": [round(e, 2) for e in oos_equity],
            "windows": windows,
        }

    def _optimize_window(self, train_data, strategy_name, param_grid, capital, bt_kwargs):
        if not param_grid:
            strategy_cls = STRATEGIES.get(strategy_name)
            if not strategy_cls:
                return {}, 0
            strategy = strategy_cls()
            signals = strategy.generate_signals(train_data)
            bt = Backtester(initial_capital=capital, **bt_kwargs)
            result = bt.run(train_data, signals)
            return {}, result.sharpe_ratio

        combos = _expand_grid(param_grid)
        best_sharpe = -999
        best_params = {}

        for params in combos:
            try:
                strategy_cls = STRATEGIES.get(strategy_name)
                strategy = strategy_cls(**params)
                signals = strategy.generate_signals(train_data)
                bt = Backtester(initial_capital=capital, **bt_kwargs)
                result = bt.run(train_data, signals)
                if result.sharpe_ratio > best_sharpe:
                    best_sharpe = result.sharpe_ratio
                    best_params = params
            except Exception:
                continue

        return best_params, best_sharpe


# ═══════════════════════════════════════════════════════════════
#  Grid Search Optimizer
# ═══════════════════════════════════════════════════════════════
class GridSearchOptimizer:
    def optimize(self, closes: List[float], strategy_name: str,
                 param_grid: Dict | None = None, capital: float = 1_000_000,
                 rank_by: str = "sharpe", **bt_kwargs) -> Dict[str, Any]:
        if param_grid is None:
            param_grid = DEFAULT_PARAM_GRIDS.get(strategy_name, {})
        if not param_grid:
            return {"error": "no param grid", "results": []}

        combos = _expand_grid(param_grid)
        results = []

        for params in combos:
            try:
                strategy_cls = STRATEGIES.get(strategy_name)
                strategy = strategy_cls(**params)
                signals = strategy.generate_signals(closes)
                bt = Backtester(initial_capital=capital, **bt_kwargs)
                result = bt.run(closes, signals)
                results.append({
                    "params": params,
                    "return_pct": round(result.total_return_pct, 2),
                    "annualized": round(result.annualized_return, 2),
                    "sharpe": round(result.sharpe_ratio, 3),
                    "sortino": round(result.sortino_ratio, 3),
                    "max_dd": round(result.max_drawdown_pct, 2),
                    "win_rate": round(result.win_rate, 1),
                    "profit_factor": round(result.profit_factor, 3),
                    "trades": result.total_trades,
                    "expectancy": round(result.expectancy, 2),
                })
            except Exception:
                continue

        rank_key = {
            "sharpe": lambda x: x["sharpe"],
            "return": lambda x: x["return_pct"],
            "sortino": lambda x: x["sortino"],
            "win_rate": lambda x: x["win_rate"],
            "profit_factor": lambda x: x["profit_factor"],
        }.get(rank_by, lambda x: x["sharpe"])

        results.sort(key=rank_key, reverse=True)

        return {
            "strategy": strategy_name,
            "total_combinations": len(combos),
            "tested": len(results),
            "rank_by": rank_by,
            "best": results[0] if results else None,
            "top_10": results[:10],
            "all_results": results,
        }


# ═══════════════════════════════════════════════════════════════
#  Param Grids & Helpers
# ═══════════════════════════════════════════════════════════════
DEFAULT_PARAM_GRIDS = {
    "golden_cross": {
        "short_period": [5, 8, 10, 15, 20],
        "long_period": [20, 30, 40, 50, 60],
    },
    "rsi": {
        "period": [7, 10, 14, 21],
        "oversold": [20, 25, 30, 35],
        "overbought": [65, 70, 75, 80],
    },
    "macd": {
        "fast": [8, 10, 12, 16],
        "slow": [20, 24, 26, 30],
        "signal_period": [7, 9, 11],
    },
    "bollinger": {
        "period": [15, 20, 25, 30],
        "num_std": [1.5, 2.0, 2.5, 3.0],
    },
}


def _expand_grid(grid: Dict[str, List]) -> List[Dict]:
    keys = list(grid.keys())
    if not keys:
        return [{}]
    combos = [{}]
    for key in keys:
        new_combos = []
        for combo in combos:
            for val in grid[key]:
                c = combo.copy()
                c[key] = val
                new_combos.append(c)
        combos = new_combos
    return combos
