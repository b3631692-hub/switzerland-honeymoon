#!/usr/bin/env python3
"""CLI entry point for stock analyzer."""
import argparse
import csv
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_analyzer.data_provider import generate_sample_data, fetch_yahoo_data, load_csv, PRESETS
from stock_analyzer.strategies import STRATEGIES, Signal
from stock_analyzer.backtester import Backtester
from stock_analyzer.risk_manager import RiskManager
from stock_analyzer.indicators import sma, ema, rsi, macd, bollinger_bands, atr, kdj, obv


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_indicators(data: dict):
    closes = data["closes"]
    highs = data["highs"]
    lows = data["lows"]

    print_header(f"📊 技術指標分析 - {data['symbol']}")
    print(f"  資料期間: {data['dates'][0]} ~ {data['dates'][-1]} ({len(closes)} 交易日)")
    print(f"  最新收盤: {closes[-1]:.2f}")
    print(f"  期間最高: {max(highs):.2f}")
    print(f"  期間最低: {min(lows):.2f}")

    sma_5 = sma(closes, 5)
    sma_10 = sma(closes, 10)
    sma_20 = sma(closes, 20)
    sma_60 = sma(closes, 60)
    rsi_val = rsi(closes, 14)
    macd_line, signal_line, hist = macd(closes)
    bb_upper, bb_mid, bb_lower = bollinger_bands(closes)
    atr_val = atr(highs, lows, closes)
    k, d, j = kdj(highs, lows, closes)

    print(f"\n  ── 移動平均線 ──")
    print(f"  SMA5:  {sma_5[-1]:.2f}" if sma_5[-1] else "  SMA5:  N/A")
    print(f"  SMA10: {sma_10[-1]:.2f}" if sma_10[-1] else "  SMA10: N/A")
    print(f"  SMA20: {sma_20[-1]:.2f}" if sma_20[-1] else "  SMA20: N/A")
    print(f"  SMA60: {sma_60[-1]:.2f}" if sma_60[-1] else "  SMA60: N/A")

    trend = "多頭排列 🟢" if sma_5[-1] and sma_20[-1] and sma_5[-1] > sma_20[-1] else "空頭排列 🔴"
    print(f"  趨勢:  {trend}")

    print(f"\n  ── RSI(14) ──")
    if rsi_val[-1] is not None:
        r = rsi_val[-1]
        status = "超買 🔴" if r > 70 else "超賣 🟢" if r < 30 else "中性 ⚪"
        print(f"  RSI:   {r:.2f} ({status})")

    print(f"\n  ── MACD(12/26/9) ──")
    if macd_line[-1] is not None:
        print(f"  MACD:  {macd_line[-1]:.4f}")
        print(f"  Signal:{signal_line[-1]:.4f}" if signal_line[-1] else "  Signal: N/A")
        print(f"  Hist:  {hist[-1]:.4f}" if hist[-1] else "  Hist:   N/A")

    print(f"\n  ── 布林帶(20, 2σ) ──")
    if bb_upper[-1] is not None:
        pos = (closes[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]) * 100
        print(f"  上軌:  {bb_upper[-1]:.2f}")
        print(f"  中軌:  {bb_mid[-1]:.2f}")
        print(f"  下軌:  {bb_lower[-1]:.2f}")
        print(f"  位置:  {pos:.1f}%")

    if atr_val[-1] is not None:
        print(f"\n  ── ATR(14) ──")
        print(f"  ATR:   {atr_val[-1]:.4f}")
        print(f"  波動率: {atr_val[-1]/closes[-1]*100:.2f}%")

    if k[-1] is not None:
        print(f"\n  ── KDJ(9,3,3) ──")
        print(f"  K: {k[-1]:.2f}  D: {d[-1]:.2f}  J: {j[-1]:.2f}")


def print_signals(data: dict, strategy_name: str):
    closes = data["closes"]
    strategy_cls = STRATEGIES.get(strategy_name)
    if not strategy_cls:
        print(f"未知策略: {strategy_name}")
        return
    strategy = strategy_cls()
    signals = strategy.generate_signals(closes)

    print_header(f"🎯 交易訊號 - {strategy.name}")
    if not signals:
        print("  無訊號產生")
        return
    buy_count = sum(1 for s in signals if s.action == Signal.BUY)
    sell_count = sum(1 for s in signals if s.action == Signal.SELL)
    print(f"  買進訊號: {buy_count} 次 | 賣出訊號: {sell_count} 次\n")
    for sig in signals[-20:]:
        icon = "🟢 買進" if sig.action == Signal.BUY else "🔴 賣出"
        date = data["dates"][sig.index] if sig.index < len(data["dates"]) else "?"
        price = closes[sig.index]
        bar = "█" * int(sig.strength * 10)
        print(f"  {date} | {icon} | 價格 {price:>10.2f} | 強度 {sig.strength:.0%} {bar}")
        print(f"           └─ {sig.reason}")


def _bt_kwargs(args):
    kw = {}
    sl = getattr(args, "stop_loss", 0)
    tp = getattr(args, "take_profit", 0)
    ts = getattr(args, "trailing_stop", 0)
    mp = getattr(args, "max_positions", 1)
    short = getattr(args, "allow_short", False)
    if sl > 0: kw["stop_loss"] = sl
    if tp > 0: kw["take_profit"] = tp
    if ts > 0: kw["trailing_stop_pct"] = ts
    if mp > 1: kw["max_positions"] = mp
    if short: kw["allow_short"] = True
    return kw


def _add_bt_args(p):
    p.add_argument("--stop-loss", type=float, default=0)
    p.add_argument("--take-profit", type=float, default=0)
    p.add_argument("--trailing-stop", type=float, default=0, help="移動停損百分比，如 0.05 = 5%%")
    p.add_argument("--max-positions", type=int, default=1, help="最大持倉數 (加碼層數)")
    p.add_argument("--allow-short", action="store_true", help="允許做空")


def print_backtest(data: dict, strategy_name: str, capital: float, bt_kw: dict):
    closes = data["closes"]
    strategy_cls = STRATEGIES.get(strategy_name)
    if not strategy_cls:
        print(f"未知策略: {strategy_name}")
        return
    strategy = strategy_cls()
    signals = strategy.generate_signals(closes)

    bt = Backtester(initial_capital=capital, **bt_kw)
    result = bt.run(closes, signals, data["dates"])

    print_header(f"📈 回測報告 - {strategy.name}")
    print(f"  期間: {data['dates'][0]} ~ {data['dates'][-1]}")
    print(f"  交易日數: {len(closes)}")

    features = []
    if bt_kw.get("trailing_stop_pct"): features.append(f"移動停損 {bt_kw['trailing_stop_pct']*100:.0f}%")
    if bt_kw.get("max_positions", 1) > 1: features.append(f"加碼 {bt_kw['max_positions']} 層")
    if bt_kw.get("allow_short"): features.append("做空")
    if features:
        print(f"  進階功能: {' | '.join(features)}")

    ret_icon = "📈" if result.total_return_pct > 0 else "📉"
    print(f"\n  ── 收益分析 ──")
    print(f"  初始資金:   ${result.initial_capital:>14,.2f}")
    print(f"  最終資金:   ${result.final_capital:>14,.2f}")
    print(f"  總報酬率:   {ret_icon} {result.total_return_pct:>+.2f}%")
    print(f"  年化報酬:   {result.annualized_return:>+.2f}%")

    print(f"\n  ── 風險指標 ──")
    print(f"  夏普比率:   {result.sharpe_ratio:.3f}")
    print(f"  Sortino:    {result.sortino_ratio:.3f}")
    print(f"  Calmar:     {result.calmar_ratio:.3f}")
    print(f"  最大回撤:   {result.max_drawdown_pct:.2f}%")
    pf_str = f"{result.profit_factor:.3f}" if result.profit_factor < 999 else "∞"
    print(f"  獲利因子:   {pf_str}")

    print(f"\n  ── 交易統計 ──")
    print(f"  總交易次數: {result.total_trades}")
    print(f"  勝率:       {result.win_rate:.1f}%")
    print(f"  獲利交易:   {result.winning_trades}")
    print(f"  虧損交易:   {result.losing_trades}")
    print(f"  平均獲利:   {result.avg_win:+.2f}%")
    print(f"  平均虧損:   {result.avg_loss:+.2f}%")
    print(f"  平均持倉:   {result.avg_holding_days:.0f} 天")
    print(f"  期望值:     ${result.expectancy:>+,.2f}/筆")
    print(f"  連續獲利:   {result.consecutive_wins} 次")
    print(f"  連續虧損:   {result.consecutive_losses} 次")

    if result.long_trades > 0 or result.short_trades > 0:
        print(f"\n  ── 多空統計 ──")
        print(f"  做多: {result.long_trades} 筆  PnL: ${result.long_pnl:>+,.2f}")
        print(f"  做空: {result.short_trades} 筆  PnL: ${result.short_pnl:>+,.2f}")

    sl_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
    tp_trades = [t for t in result.trades if t.exit_reason == "take_profit"]
    ts_trades = [t for t in result.trades if t.exit_reason == "trailing_stop"]
    if sl_trades or tp_trades or ts_trades:
        print(f"\n  ── 停損停利統計 ──")
        if sl_trades:
            sl_avg = sum(t.pnl_pct for t in sl_trades) / len(sl_trades)
            print(f"  固定停損:   {len(sl_trades)} 次  平均 {sl_avg:+.2f}%")
        if ts_trades:
            ts_avg = sum(t.pnl_pct for t in ts_trades) / len(ts_trades)
            print(f"  移動停損:   {len(ts_trades)} 次  平均 {ts_avg:+.2f}%")
        if tp_trades:
            tp_avg = sum(t.pnl_pct for t in tp_trades) / len(tp_trades)
            print(f"  停利觸發:   {len(tp_trades)} 次  平均 {tp_avg:+.2f}%")

    if result.trades:
        reason_map = {"stop_loss": "🛑停損", "take_profit": "🎯停利", "trailing_stop": "🔄移停",
                      "signal": "📊策略", "end_of_data": "⏹結束"}
        print(f"\n  ── 最近交易 ──")
        for t in result.trades[-10:]:
            entry_date = data["dates"][t.entry_idx] if t.entry_idx < len(data["dates"]) else "?"
            exit_date = data["dates"][t.exit_idx] if t.exit_idx and t.exit_idx < len(data["dates"]) else "?"
            icon = "✅" if t.pnl > 0 else "❌"
            reason = reason_map.get(t.exit_reason, t.exit_reason)
            direction = "📈" if t.direction == "LONG" else "📉"
            print(f"  {icon}{direction} {entry_date}→{exit_date} | {reason} | {t.entry_price:.2f}→{t.exit_price:.2f} | {t.pnl_pct:+.2f}% (${t.pnl:+,.2f})")

    return result


def print_montecarlo(data: dict, strategy_name: str, capital: float, bt_kw: dict, n_sims: int):
    from stock_analyzer.advanced import MonteCarloSimulator

    closes = data["closes"]
    strategy_cls = STRATEGIES.get(strategy_name, STRATEGIES["composite"])
    strategy = strategy_cls()
    signals = strategy.generate_signals(closes)
    bt = Backtester(initial_capital=capital, **bt_kw)
    result = bt.run(closes, signals, data["dates"])

    if not result.trades:
        print("  無交易，無法執行 Monte Carlo")
        return

    mc = MonteCarloSimulator(n_simulations=n_sims, seed=42)
    mc_result = mc.run(result.trades, capital)

    print_header(f"🎲 Monte Carlo 模擬 ({n_sims} 次) - {strategy.name}")
    fc = mc_result["final_capital_stats"]
    dd = mc_result["max_drawdown_stats"]
    print(f"  原始交易數:   {mc_result['n_trades']}")
    print(f"\n  ── 最終資金分佈 ──")
    print(f"  平均:    ${fc['mean']:>14,.2f}")
    print(f"  中位數:  ${fc['median']:>14,.2f}")
    print(f"  5%ile:   ${fc['p5']:>14,.2f}")
    print(f"  95%ile:  ${fc['p95']:>14,.2f}")
    print(f"  最差:    ${fc['min']:>14,.2f}")
    print(f"  最佳:    ${fc['max']:>14,.2f}")
    print(f"\n  ── 最大回撤分佈 ──")
    print(f"  平均:    {dd['mean']:.2f}%")
    print(f"  中位數:  {dd['median']:.2f}%")
    print(f"  最差:    {dd['worst']:.2f}%")
    print(f"\n  ── 風險評估 ──")
    print(f"  獲利機率:    {mc_result['probability_of_profit']:.1f}%")
    print(f"  破產機率:    {mc_result['probability_of_ruin']:.1f}% (本金腰斬)")
    sr = mc_result['sharpe_stats']
    print(f"  夏普中位數:  {sr['median']:.3f}")


def print_walkforward(data: dict, strategy_name: str, capital: float, bt_kw: dict, n_windows: int):
    from stock_analyzer.advanced import WalkForwardAnalyzer

    wf = WalkForwardAnalyzer(n_windows=n_windows)
    wf_result = wf.run(data["closes"], strategy_name, capital, **bt_kw)

    if "error" in wf_result:
        print(f"  ❌ {wf_result['error']}")
        return

    print_header(f"📐 Walk-Forward 分析 ({wf_result['n_windows']} 窗口)")
    print(f"  訓練/測試比: {wf_result['train_ratio']*100:.0f}% / {(1-wf_result['train_ratio'])*100:.0f}%")
    print(f"  初始資金:    ${wf_result['initial_capital']:>14,.2f}")
    print(f"  最終資金:    ${wf_result['final_capital']:>14,.2f}")
    print(f"  累計報酬:    {wf_result['total_return_pct']:+.2f}%")
    print(f"  平均OOS報酬: {wf_result['avg_oos_return']:+.2f}%")

    print(f"\n  {'窗口':>4} | {'訓練夏普':>8} | {'OOS報酬':>8} | {'OOS夏普':>8} | {'交易':>4} | {'勝率':>6} | {'最大回撤':>8} | 最佳參數")
    print(f"  {'─'*4}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*4}─┼─{'─'*6}─┼─{'─'*8}─┼─{'─'*20}")
    for w in wf_result["windows"]:
        params_str = ", ".join(f"{k}={v}" for k, v in w["best_params"].items()) or "default"
        icon = "✅" if w["oos_return_pct"] > 0 else "❌"
        print(f"  {icon}{w['window']:>2}  | {w['train_sharpe']:>+8.3f} | {w['oos_return_pct']:>+7.2f}% | {w['oos_sharpe']:>+8.3f} | {w['oos_trades']:>4} | {w['oos_win_rate']:>5.1f}% | {w['oos_max_dd']:>7.2f}% | {params_str}")


def print_optimize(data: dict, strategy_name: str, capital: float, bt_kw: dict, rank_by: str):
    from stock_analyzer.advanced import GridSearchOptimizer

    opt = GridSearchOptimizer()
    opt_result = opt.optimize(data["closes"], strategy_name, capital=capital, rank_by=rank_by, **bt_kw)

    if "error" in opt_result:
        print(f"  ❌ {opt_result['error']}")
        return

    print_header(f"🔍 Grid Search 參數最佳化 - {strategy_name}")
    print(f"  測試組合數: {opt_result['total_combinations']}")
    print(f"  排序依據:   {rank_by}")

    if opt_result["best"]:
        b = opt_result["best"]
        params_str = ", ".join(f"{k}={v}" for k, v in b["params"].items())
        print(f"\n  🏆 最佳參數: {params_str}")
        print(f"     報酬 {b['return_pct']:+.2f}% | 夏普 {b['sharpe']:.3f} | Sortino {b['sortino']:.3f} | 勝率 {b['win_rate']:.1f}% | 回撤 {b['max_dd']:.2f}%")

    print(f"\n  {'排名':>4} | {'報酬':>8} | {'夏普':>7} | {'Sortino':>7} | {'勝率':>6} | {'回撤':>7} | {'交易':>4} | 參數")
    print(f"  {'─'*4}─┼─{'─'*8}─┼─{'─'*7}─┼─{'─'*7}─┼─{'─'*6}─┼─{'─'*7}─┼─{'─'*4}─┼─{'─'*20}")
    for i, r in enumerate(opt_result["top_10"]):
        params_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        icon = "👑" if i == 0 else f"  "
        print(f"  {icon}{i+1:>2} | {r['return_pct']:>+7.2f}% | {r['sharpe']:>+7.3f} | {r['sortino']:>+7.3f} | {r['win_rate']:>5.1f}% | {r['max_dd']:>6.2f}% | {r['trades']:>4} | {params_str}")


def run_full_analysis(data: dict, capital: float):
    print_indicators(data)
    print()
    best_result = None
    best_strategy = None
    for name, cls in STRATEGIES.items():
        if name == "kdj":
            continue
        strategy = cls()
        signals = strategy.generate_signals(data["closes"])
        bt = Backtester(initial_capital=capital)
        result = bt.run(data["closes"], signals, data["dates"])
        if best_result is None or result.total_return_pct > best_result.total_return_pct:
            best_result = result
            best_strategy = name

    print_header("🏆 策略比較")
    for name, cls in STRATEGIES.items():
        if name == "kdj":
            continue
        strategy = cls()
        signals = strategy.generate_signals(data["closes"])
        bt = Backtester(initial_capital=capital)
        result = bt.run(data["closes"], signals, data["dates"])
        icon = "👑" if name == best_strategy else "  "
        print(f"  {icon} {strategy.name:<30} | 報酬 {result.total_return_pct:>+8.2f}% | 夏普 {result.sharpe_ratio:>6.3f} | 勝率 {result.win_rate:>5.1f}% | 交易 {result.total_trades:>3}筆")

    print(f"\n  🏆 最佳策略: {best_strategy}")
    print_backtest(data, best_strategy, capital, {})

    rm = RiskManager()
    if best_result and best_result.equity_curve:
        dd_check = rm.check_drawdown(best_result.equity_curve)
        print(f"\n  ── 風險檢查 ──")
        print(f"  當前回撤: {dd_check['current_drawdown_pct']:.2f}%")
        print(f"  最大回撤: {dd_check['max_drawdown_pct']:.2f}%")
        print(f"  狀態: {dd_check['action']}")

    if best_result and best_result.win_rate > 0:
        kelly = rm.kelly_criterion(
            best_result.win_rate / 100,
            abs(best_result.avg_win) if best_result.avg_win else 1,
            abs(best_result.avg_loss) if best_result.avg_loss else 1,
        )
        print(f"\n  ── 建議部位 ──")
        print(f"  Kelly 建議: {kelly*100:.1f}% 倉位")
        print(f"  建議金額:   ${capital * kelly:,.0f}")


def export_trades(data: dict, strategy_name: str, capital: float, bt_kw: dict):
    """Export trades to CSV and equity curve to a separate CSV."""
    closes = data["closes"]
    dates = data["dates"]
    symbol = data.get("symbol", "stock")

    strategy_cls = STRATEGIES.get(strategy_name)
    if not strategy_cls:
        print(f"未知策略: {strategy_name}")
        return
    strategy = strategy_cls()
    signals = strategy.generate_signals(closes)

    bt = Backtester(initial_capital=capital, **bt_kw)
    result = bt.run(closes, signals, dates)

    # --- Export trades CSV ---
    trades_file = f"{symbol}_trades.csv"
    with open(trades_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "entry_date", "exit_date", "direction", "entry_price", "exit_price",
            "stop_loss", "take_profit", "exit_reason", "pnl", "pnl_pct", "holding_days"
        ])
        for t in result.trades:
            entry_date = dates[t.entry_idx] if t.entry_idx < len(dates) else ""
            exit_date = dates[t.exit_idx] if t.exit_idx is not None and t.exit_idx < len(dates) else ""
            holding_days = (t.exit_idx - t.entry_idx) if t.exit_idx is not None else 0
            writer.writerow([
                entry_date,
                exit_date,
                t.direction,
                round(t.entry_price, 2),
                round(t.exit_price, 2) if t.exit_price is not None else "",
                round(t.stop_loss_price, 2) if t.stop_loss_price is not None else "",
                round(t.take_profit_price, 2) if t.take_profit_price is not None else "",
                t.exit_reason,
                round(t.pnl, 2),
                round(t.pnl_pct, 2),
                holding_days,
            ])

    # --- Export equity curve CSV ---
    equity_file = f"{symbol}_equity.csv"
    with open(equity_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "equity"])
        for i, eq in enumerate(result.equity_curve):
            date = dates[i] if i < len(dates) else ""
            writer.writerow([date, round(eq, 2)])

    print_header(f"📋 交易紀錄匯出 - {strategy.name}")
    print(f"  策略:       {strategy.name}")
    print(f"  交易筆數:   {len(result.trades)}")
    print(f"  交易紀錄:   {trades_file}")
    print(f"  權益曲線:   {equity_file}")
    print(f"  總報酬率:   {result.total_return_pct:+.2f}%")


def main():
    parser = argparse.ArgumentParser(
        description="📊 無情獲利股票分析系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python -m stock_analyzer.main analyze --preset uptrend
  python -m stock_analyzer.main backtest --preset volatile --strategy macd --trailing-stop 0.05 --allow-short
  python -m stock_analyzer.main backtest --preset uptrend --strategy bollinger --max-positions 3
  python -m stock_analyzer.main montecarlo --preset volatile --strategy macd --n 1000
  python -m stock_analyzer.main walkforward --preset uptrend --strategy golden_cross --windows 5
  python -m stock_analyzer.main optimize --strategy golden_cross --rank-by sharpe
  python -m stock_analyzer.main full --preset uptrend --capital 1000000
  python -m stock_analyzer.main server --port 8888

策略: golden_cross, rsi, macd, bollinger, kdj, composite, ema_cross, volume_breakout
資料: uptrend, volatile, bearish, default
        """
    )
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="技術指標分析")
    p_analyze.add_argument("--symbol", type=str)
    p_analyze.add_argument("--csv", type=str)
    p_analyze.add_argument("--preset", type=str, default="default")

    p_signals = sub.add_parser("signals", help="交易訊號")
    p_signals.add_argument("--symbol", type=str)
    p_signals.add_argument("--csv", type=str)
    p_signals.add_argument("--preset", type=str, default="default")
    p_signals.add_argument("--strategy", type=str, default="composite")

    p_bt = sub.add_parser("backtest", help="策略回測")
    p_bt.add_argument("--symbol", type=str)
    p_bt.add_argument("--csv", type=str)
    p_bt.add_argument("--preset", type=str, default="default")
    p_bt.add_argument("--strategy", type=str, default="composite")
    p_bt.add_argument("--capital", type=float, default=1_000_000)
    _add_bt_args(p_bt)

    p_mc = sub.add_parser("montecarlo", help="Monte Carlo 模擬")
    p_mc.add_argument("--symbol", type=str)
    p_mc.add_argument("--csv", type=str)
    p_mc.add_argument("--preset", type=str, default="default")
    p_mc.add_argument("--strategy", type=str, default="composite")
    p_mc.add_argument("--capital", type=float, default=1_000_000)
    p_mc.add_argument("--n", type=int, default=500, help="模擬次數")
    _add_bt_args(p_mc)

    p_wf = sub.add_parser("walkforward", help="Walk-Forward 分析")
    p_wf.add_argument("--symbol", type=str)
    p_wf.add_argument("--csv", type=str)
    p_wf.add_argument("--preset", type=str, default="default")
    p_wf.add_argument("--strategy", type=str, default="golden_cross")
    p_wf.add_argument("--capital", type=float, default=1_000_000)
    p_wf.add_argument("--windows", type=int, default=5, help="分析窗口數")
    _add_bt_args(p_wf)

    p_opt = sub.add_parser("optimize", help="Grid Search 參數最佳化")
    p_opt.add_argument("--symbol", type=str)
    p_opt.add_argument("--csv", type=str)
    p_opt.add_argument("--preset", type=str, default="default")
    p_opt.add_argument("--strategy", type=str, default="golden_cross")
    p_opt.add_argument("--capital", type=float, default=1_000_000)
    p_opt.add_argument("--rank-by", type=str, default="sharpe", choices=["sharpe", "return", "sortino", "win_rate", "profit_factor"])
    _add_bt_args(p_opt)

    p_full = sub.add_parser("full", help="完整分析報告")
    p_full.add_argument("--symbol", type=str)
    p_full.add_argument("--csv", type=str)
    p_full.add_argument("--preset", type=str, default="default")
    p_full.add_argument("--capital", type=float, default=1_000_000)

    p_server = sub.add_parser("server", help="啟動網頁儀表板")
    p_server.add_argument("--port", type=int, default=8080)
    p_server.add_argument("--host", type=str, default="0.0.0.0")

    p_json = sub.add_parser("json", help="JSON 輸出")
    p_json.add_argument("--symbol", type=str)
    p_json.add_argument("--csv", type=str)
    p_json.add_argument("--preset", type=str, default="default")
    p_json.add_argument("--strategy", type=str, default="composite")
    p_json.add_argument("--capital", type=float, default=1_000_000)

    p_export = sub.add_parser("export", help="匯出交易紀錄與權益曲線至 CSV")
    p_export.add_argument("--symbol", type=str)
    p_export.add_argument("--csv", type=str)
    p_export.add_argument("--preset", type=str, default="default")
    p_export.add_argument("--strategy", type=str, default="composite")
    p_export.add_argument("--capital", type=float, default=1_000_000)
    _add_bt_args(p_export)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "server":
        from stock_analyzer.server import run_server
        run_server(args.host, args.port)
        return

    data = _load_data(args)
    if not data:
        print("❌ 無法載入資料")
        return

    if args.command == "analyze":
        print_indicators(data)
    elif args.command == "signals":
        print_signals(data, args.strategy)
    elif args.command == "backtest":
        print_backtest(data, args.strategy, args.capital, _bt_kwargs(args))
    elif args.command == "montecarlo":
        print_montecarlo(data, args.strategy, args.capital, _bt_kwargs(args), args.n)
    elif args.command == "walkforward":
        print_walkforward(data, args.strategy, args.capital, _bt_kwargs(args), args.windows)
    elif args.command == "optimize":
        print_optimize(data, args.strategy, args.capital, _bt_kwargs(args), args.rank_by)
    elif args.command == "full":
        run_full_analysis(data, args.capital)
    elif args.command == "export":
        export_trades(data, args.strategy, args.capital, _bt_kwargs(args))
    elif args.command == "json":
        output = _build_json(data, args.strategy, args.capital)
        print(json.dumps(output, ensure_ascii=False, indent=2))


def _load_data(args) -> dict | None:
    if hasattr(args, "symbol") and args.symbol:
        data = fetch_yahoo_data(args.symbol)
        if data:
            return data
        print(f"⚠️  無法從 Yahoo Finance 取得 {args.symbol}，改用模擬資料")
    if hasattr(args, "csv") and args.csv:
        return load_csv(args.csv)
    preset = getattr(args, "preset", "default")
    if preset in PRESETS:
        return PRESETS[preset]()
    return generate_sample_data()


def _build_json(data: dict, strategy_name: str, capital: float) -> dict:
    from stock_analyzer.indicators import sma as _sma, rsi as _rsi, macd as _macd, bollinger_bands as _bb
    closes = data["closes"]
    strategy_cls = STRATEGIES.get(strategy_name)
    strategy = strategy_cls() if strategy_cls else STRATEGIES["composite"]()
    signals = strategy.generate_signals(closes)
    bt = Backtester(initial_capital=capital)
    result = bt.run(closes, signals, data["dates"])
    sma20 = _sma(closes, 20)
    sma60 = _sma(closes, 60)
    rsi14 = _rsi(closes, 14)
    macd_l, sig_l, hist_l = _macd(closes)
    bb_u, bb_m, bb_lo = _bb(closes)
    return {
        "data": data,
        "indicators": {"sma20": sma20, "sma60": sma60, "rsi": rsi14,
                        "macd": macd_l, "macd_signal": sig_l, "macd_hist": hist_l,
                        "bb_upper": bb_u, "bb_middle": bb_m, "bb_lower": bb_lo},
        "signals": [s.to_dict() for s in signals],
        "backtest": result.to_dict(),
        "strategy": strategy.name,
    }


if __name__ == "__main__":
    main()
