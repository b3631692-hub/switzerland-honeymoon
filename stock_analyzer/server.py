"""HTTP server: dashboard + API for analysis, Monte Carlo, Walk-Forward, Grid Search."""
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .data_provider import generate_sample_data, fetch_yahoo_data, PRESETS
from .strategies import STRATEGIES
from .backtester import Backtester
from .advanced import MonteCarloSimulator, WalkForwardAnalyzer, GridSearchOptimizer, DEFAULT_PARAM_GRIDS
from .indicators import sma, ema, rsi, macd, bollinger_bands, atr, kdj, obv

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


def _get_data(params):
    symbol = params.get("symbol", [""])[0]
    preset = params.get("preset", ["default"])[0]
    if symbol:
        data = fetch_yahoo_data(symbol)
        if data:
            return data
    if preset in PRESETS:
        return PRESETS[preset]()
    return generate_sample_data()


def _bt_kwargs(params):
    sl = float(params.get("stop_loss", ["0"])[0])
    tp = float(params.get("take_profit", ["0"])[0])
    ts = float(params.get("trailing_stop", ["0"])[0])
    mp = int(params.get("max_positions", ["1"])[0])
    short = params.get("allow_short", ["0"])[0] in ("1", "true")
    kw = {}
    if sl > 0:
        kw["stop_loss"] = sl
    if tp > 0:
        kw["take_profit"] = tp
    if ts > 0:
        kw["trailing_stop_pct"] = ts
    if mp > 1:
        kw["max_positions"] = mp
    if short:
        kw["allow_short"] = True
    return kw


class APIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        routes = {
            "/api/analyze": self._handle_analyze,
            "/api/montecarlo": self._handle_montecarlo,
            "/api/walkforward": self._handle_walkforward,
            "/api/optimize": self._handle_optimize,
            "/api/strategies": lambda p: self._json_response({"strategies": list(STRATEGIES.keys())}),
            "/api/presets": lambda p: self._json_response({"presets": list(PRESETS.keys())}),
        }

        if path in routes:
            routes[path](params)
        elif path == "/" or path == "/dashboard.html":
            self._serve_dashboard()
        else:
            self._serve_static(path)

    def _handle_analyze(self, params):
        data = _get_data(params)
        strategy_name = params.get("strategy", ["composite"])[0]
        capital = float(params.get("capital", ["1000000"])[0])
        bt_kw = _bt_kwargs(params)

        closes = data["closes"]
        highs = data["highs"]
        lows = data["lows"]
        volumes = data["volumes"]

        strategy_cls = STRATEGIES.get(strategy_name, STRATEGIES["composite"])
        strategy = strategy_cls()
        signals = strategy.generate_signals(closes)

        bt = Backtester(initial_capital=capital, **bt_kw)
        result = bt.run(closes, signals, data["dates"])

        sma5 = sma(closes, 5)
        sma10 = sma(closes, 10)
        sma20 = sma(closes, 20)
        sma60 = sma(closes, 60)
        rsi14 = rsi(closes, 14)
        macd_l, sig_l, hist_l = macd(closes)
        bb_u, bb_m, bb_lo = bollinger_bands(closes)
        atr14 = atr(highs, lows, closes)
        k, d, j = kdj(highs, lows, closes)
        obv_vals = obv(closes, volumes)

        sl_v = bt_kw.get("stop_loss")
        tp_v = bt_kw.get("take_profit")
        ts_v = bt_kw.get("trailing_stop_pct")

        self._json_response({
            "data": data,
            "indicators": {
                "sma5": sma5, "sma10": sma10, "sma20": sma20, "sma60": sma60,
                "rsi": rsi14,
                "macd": macd_l, "macd_signal": sig_l, "macd_hist": hist_l,
                "bb_upper": bb_u, "bb_middle": bb_m, "bb_lower": bb_lo,
                "atr": atr14, "kdj_k": k, "kdj_d": d, "kdj_j": j, "obv": obv_vals,
            },
            "signals": [s.to_dict() for s in signals],
            "backtest": result.to_dict(),
            "strategy_name": strategy.name,
            "config": {
                "stop_loss": sl_v,
                "take_profit": tp_v,
                "trailing_stop": ts_v,
                "max_positions": bt_kw.get("max_positions", 1),
                "allow_short": bt_kw.get("allow_short", False),
            },
        })

    def _handle_montecarlo(self, params):
        data = _get_data(params)
        strategy_name = params.get("strategy", ["composite"])[0]
        capital = float(params.get("capital", ["1000000"])[0])
        n_sims = int(params.get("n", ["500"])[0])
        bt_kw = _bt_kwargs(params)

        strategy_cls = STRATEGIES.get(strategy_name, STRATEGIES["composite"])
        strategy = strategy_cls()
        signals = strategy.generate_signals(data["closes"])
        bt = Backtester(initial_capital=capital, **bt_kw)
        result = bt.run(data["closes"], signals)

        mc = MonteCarloSimulator(n_simulations=min(n_sims, 2000), seed=42)
        mc_result = mc.run(result.trades, capital)
        self._json_response(mc_result)

    def _handle_walkforward(self, params):
        data = _get_data(params)
        strategy_name = params.get("strategy", ["composite"])[0]
        capital = float(params.get("capital", ["1000000"])[0])
        n_windows = int(params.get("windows", ["5"])[0])
        bt_kw = _bt_kwargs(params)

        wf = WalkForwardAnalyzer(n_windows=min(n_windows, 10))
        wf_result = wf.run(data["closes"], strategy_name, capital, **bt_kw)
        self._json_response(wf_result)

    def _handle_optimize(self, params):
        data = _get_data(params)
        strategy_name = params.get("strategy", ["golden_cross"])[0]
        capital = float(params.get("capital", ["1000000"])[0])
        rank_by = params.get("rank_by", ["sharpe"])[0]
        bt_kw = _bt_kwargs(params)

        opt = GridSearchOptimizer()
        opt_result = opt.optimize(data["closes"], strategy_name, capital=capital, rank_by=rank_by, **bt_kw)
        self._json_response(opt_result)

    def _json_response(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_dashboard(self):
        filepath = os.path.join(DASHBOARD_DIR, "dashboard.html")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "Dashboard not found")

    def _serve_static(self, path):
        filepath = os.path.join(DASHBOARD_DIR, path.lstrip("/"))
        if os.path.exists(filepath) and os.path.isfile(filepath):
            with open(filepath, "rb") as f:
                content = f.read()
            ct = "text/html"
            if filepath.endswith(".js"):
                ct = "application/javascript"
            elif filepath.endswith(".css"):
                ct = "text/css"
            elif filepath.endswith(".json"):
                ct = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def run_server(host: str = "0.0.0.0", port: int = 8080):
    print(f"🚀 無情獲利分析系統啟動中...")
    print(f"📊 儀表板:       http://{host}:{port}/")
    print(f"🔌 分析 API:     http://{host}:{port}/api/analyze?preset=uptrend&strategy=composite")
    print(f"🎲 Monte Carlo:  http://{host}:{port}/api/montecarlo?preset=uptrend&strategy=macd&n=500")
    print(f"📐 Walk-Forward: http://{host}:{port}/api/walkforward?preset=uptrend&strategy=macd")
    print(f"🔍 Grid Search:  http://{host}:{port}/api/optimize?strategy=golden_cross")
    print(f"   按 Ctrl+C 停止伺服器")
    server = HTTPServer((host, port), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 伺服器已停止")
        server.server_close()
