"""Simple HTTP server that serves the dashboard and provides API endpoints."""
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .data_provider import generate_sample_data, fetch_yahoo_data, PRESETS
from .strategies import STRATEGIES
from .backtester import Backtester
from .indicators import sma, ema, rsi, macd, bollinger_bands, atr, kdj, obv


DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


class APIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/analyze":
            self._handle_analyze(params)
        elif path == "/api/strategies":
            self._json_response({"strategies": list(STRATEGIES.keys())})
        elif path == "/api/presets":
            self._json_response({"presets": list(PRESETS.keys())})
        elif path == "/" or path == "/dashboard.html":
            self._serve_dashboard()
        else:
            self._serve_static(path)

    def _handle_analyze(self, params):
        symbol = params.get("symbol", [""])[0]
        preset = params.get("preset", ["default"])[0]
        strategy_name = params.get("strategy", ["composite"])[0]
        capital = float(params.get("capital", ["1000000"])[0])
        stop_loss = float(params.get("stop_loss", ["0"])[0])
        take_profit = float(params.get("take_profit", ["0"])[0])

        data = None
        if symbol:
            data = fetch_yahoo_data(symbol)
        if not data:
            if preset in PRESETS:
                data = PRESETS[preset]()
            else:
                data = generate_sample_data()

        closes = data["closes"]
        highs = data["highs"]
        lows = data["lows"]
        volumes = data["volumes"]

        strategy_cls = STRATEGIES.get(strategy_name, STRATEGIES["composite"])
        strategy = strategy_cls()
        signals = strategy.generate_signals(closes)

        bt = Backtester(
            initial_capital=capital,
            stop_loss=stop_loss if stop_loss > 0 else None,
            take_profit=take_profit if take_profit > 0 else None,
        )
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

        response = {
            "data": data,
            "indicators": {
                "sma5": sma5, "sma10": sma10, "sma20": sma20, "sma60": sma60,
                "rsi": rsi14,
                "macd": macd_l, "macd_signal": sig_l, "macd_hist": hist_l,
                "bb_upper": bb_u, "bb_middle": bb_m, "bb_lower": bb_lo,
                "atr": atr14,
                "kdj_k": k, "kdj_d": d, "kdj_j": j,
                "obv": obv_vals,
            },
            "signals": [s.to_dict() for s in signals],
            "backtest": result.to_dict(),
            "strategy_name": strategy.name,
            "config": {
                "stop_loss": stop_loss if stop_loss > 0 else None,
                "take_profit": take_profit if take_profit > 0 else None,
            },
        }
        self._json_response(response)

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
    print(f"📊 儀表板: http://{host}:{port}/")
    print(f"🔌 API:    http://{host}:{port}/api/analyze?preset=uptrend&strategy=composite")
    print(f"   按 Ctrl+C 停止伺服器")
    server = HTTPServer((host, port), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 伺服器已停止")
        server.server_close()
