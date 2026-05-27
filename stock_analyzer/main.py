#!/usr/bin/env python3
"""CLI entry point for stock analyzer."""
import argparse
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
    volumes = data["volumes"]

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


def print_backtest(data: dict, strategy_name: str, capital: float, stop_loss: float, take_profit: float):
    closes = data["closes"]
    strategy_cls = STRATEGIES.get(strategy_name)
    if not strategy_cls:
        print(f"未知策略: {strategy_name}")
        return

    strategy = strategy_cls()
    signals = strategy.generate_signals(closes)

    bt = Backtester(
        initial_capital=capital,
        stop_loss=stop_loss if stop_loss > 0 else None,
        take_profit=take_profit if take_profit > 0 else None,
    )
    result = bt.run(closes, signals, data["dates"])

    print_header(f"📈 回測報告 - {strategy.name}")
    print(f"  期間: {data['dates'][0]} ~ {data['dates'][-1]}")
    print(f"  交易日數: {len(closes)}")

    ret_icon = "📈" if result.total_return_pct > 0 else "📉"
    print(f"\n  ── 收益分析 ──")
    print(f"  初始資金:   ${result.initial_capital:>14,.2f}")
    print(f"  最終資金:   ${result.final_capital:>14,.2f}")
    print(f"  總報酬率:   {ret_icon} {result.total_return_pct:>+.2f}%")
    print(f"  年化報酬:   {result.annualized_return:>+.2f}%")

    print(f"\n  ── 風險指標 ──")
    print(f"  夏普比率:   {result.sharpe_ratio:.3f}")
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

    if result.trades:
        print(f"\n  ── 最近交易 ──")
        for t in result.trades[-10:]:
            entry_date = data["dates"][t.entry_idx] if t.entry_idx < len(data["dates"]) else "?"
            exit_date = data["dates"][t.exit_idx] if t.exit_idx and t.exit_idx < len(data["dates"]) else "?"
            icon = "✅" if t.pnl > 0 else "❌"
            print(f"  {icon} {entry_date} → {exit_date} | 買 {t.entry_price:.2f} → 賣 {t.exit_price:.2f} | {t.pnl_pct:+.2f}% (${t.pnl:+,.2f})")


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
    print_backtest(data, best_strategy, capital, 0, 0)

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


def main():
    parser = argparse.ArgumentParser(
        description="📊 無情獲利股票分析系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python -m stock_analyzer.main analyze --preset uptrend
  python -m stock_analyzer.main analyze --symbol AAPL
  python -m stock_analyzer.main signals --preset volatile --strategy macd
  python -m stock_analyzer.main backtest --preset default --strategy composite --capital 500000
  python -m stock_analyzer.main full --symbol TSLA --capital 1000000
  python -m stock_analyzer.main server --port 8888

策略選項: golden_cross, rsi, macd, bollinger, kdj, composite
資料預設: uptrend, volatile, bearish, default
        """
    )
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="顯示技術指標分析")
    p_analyze.add_argument("--symbol", type=str, help="股票代碼 (Yahoo Finance)")
    p_analyze.add_argument("--csv", type=str, help="CSV 檔案路徑")
    p_analyze.add_argument("--preset", type=str, default="default", help="預設資料集")

    p_signals = sub.add_parser("signals", help="產生交易訊號")
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
    p_bt.add_argument("--stop-loss", type=float, default=0)
    p_bt.add_argument("--take-profit", type=float, default=0)

    p_full = sub.add_parser("full", help="完整分析報告")
    p_full.add_argument("--symbol", type=str)
    p_full.add_argument("--csv", type=str)
    p_full.add_argument("--preset", type=str, default="default")
    p_full.add_argument("--capital", type=float, default=1_000_000)

    p_server = sub.add_parser("server", help="啟動網頁儀表板")
    p_server.add_argument("--port", type=int, default=8080)
    p_server.add_argument("--host", type=str, default="0.0.0.0")

    p_json = sub.add_parser("json", help="輸出 JSON 格式 (供 API 使用)")
    p_json.add_argument("--symbol", type=str)
    p_json.add_argument("--csv", type=str)
    p_json.add_argument("--preset", type=str, default="default")
    p_json.add_argument("--strategy", type=str, default="composite")
    p_json.add_argument("--capital", type=float, default=1_000_000)

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
        print_backtest(data, args.strategy, args.capital, args.stop_loss, args.take_profit)
    elif args.command == "full":
        run_full_analysis(data, args.capital)
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
        "indicators": {
            "sma20": sma20,
            "sma60": sma60,
            "rsi": rsi14,
            "macd": macd_l,
            "macd_signal": sig_l,
            "macd_hist": hist_l,
            "bb_upper": bb_u,
            "bb_middle": bb_m,
            "bb_lower": bb_lo,
        },
        "signals": [s.to_dict() for s in signals],
        "backtest": result.to_dict(),
        "strategy": strategy.name,
    }


if __name__ == "__main__":
    main()
