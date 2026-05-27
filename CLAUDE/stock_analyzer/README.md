# ⚡ 無情獲利股票分析系統

> 純 Python 實作，零外部依賴，完整回測引擎 + 互動式網頁儀表板

---

## 快速開始

```bash
# 啟動網頁儀表板
cd CLAUDE
python3 -m stock_analyzer.main server --port 8080
# 開啟 http://localhost:8080

# 或使用 CLI
python3 -m stock_analyzer.main full --preset uptrend --capital 1000000
```

---

## 系統架構

```
CLAUDE/stock_analyzer/
├── indicators.py      # 技術指標引擎 (6KB)
├── strategies.py      # 交易策略庫 (17KB)
├── backtester.py      # 回測引擎 (23KB)
├── advanced.py        # 進階演算法 (19KB)
├── risk_manager.py    # 風險管理 + 評分 (8KB)
├── data_provider.py   # 資料來源 (5KB)
├── server.py          # HTTP API 伺服器 (13KB)
├── main.py            # CLI 命令列介面 (26KB)
├── dashboard.html     # 網頁儀表板 (42KB)
└── requirements.txt   # 無外部依賴
```

---

## 功能總覽

### 1. 技術指標 (9 種)

| 指標 | 說明 | 用途 |
|------|------|------|
| SMA | 簡單移動平均線 | 趨勢判斷 |
| EMA | 指數移動平均線 | 靈敏趨勢追蹤 |
| RSI | 相對強弱指標 | 超買超賣判斷 |
| MACD | 移動平均收斂擴散 | 動能與趨勢轉折 |
| Bollinger Bands | 布林帶 | 波動率與價格區間 |
| KDJ | 隨機指標 | 短線超買超賣 |
| ATR | 平均真實範圍 | 波動率衡量 |
| OBV | 量能累積指標 | 量價關係確認 |
| VWAP | 成交量加權均價 | 機構成本判斷 |

### 2. 交易策略 (9 種)

| 策略 | CLI 名稱 | 說明 |
|------|----------|------|
| SMA 均線交叉 | `golden_cross` | SMA10/SMA30 黃金交叉 / 死亡交叉 |
| EMA 交叉 | `ema_cross` | EMA12/EMA26 交叉 + EMA200 趨勢濾網 |
| RSI 反轉 | `rsi` | RSI(14) 超買 >70 / 超賣 <30 反轉訊號 |
| MACD 柱狀 | `macd` | MACD 柱狀圖翻正/翻負 |
| 布林帶反彈 | `bollinger` | 價格觸碰布林帶上下軌反彈 |
| KDJ 交叉 | `kdj` | K/D 線交叉 + J 值過濾 |
| 量價突破 | `volume_breakout` | 2x 均量 + 突破 20 日高低點 |
| 風報比過濾 | `rr_filtered` | 綜合策略 + R:R >= 2.0 過濾 |
| 綜合策略 | `composite` | 多策略加權投票，>=2 策略共振才進場 |

### 3. 回測引擎

#### 基本功能
- **交易成本模擬**: 手續費 0.1425% + 交易稅 0.3% + 滑價 0.1%
- **固定停損/停利**: 設定百分比自動出場
- **權益曲線追蹤**: 逐日 mark-to-market

#### 進階功能
| 功能 | 參數 | 說明 |
|------|------|------|
| 移動停損 | `--trailing-stop 0.05` | 停損點跟隨最高價上移，鎖住利潤 |
| 加碼 | `--max-positions 3` | 分批建倉，最多 N 層 |
| 做空 | `--allow-short` | SELL 訊號時開空單 |
| Kelly 倉位 | `sizing_mode="kelly"` | 根據歷史勝率動態計算倉位 |
| ATR 倉位 | `sizing_mode="atr"` | 根據 ATR 波動率動態計算倉位 |

#### 績效指標
- 總報酬率 / 年化報酬
- 夏普比率 (Sharpe Ratio)
- Sortino Ratio
- Calmar Ratio
- 最大回撤 (Max Drawdown)
- 勝率 / 獲利因子 (Profit Factor)
- 期望值 / 平均持倉天數
- 連續獲利 / 連續虧損
- 多空分離統計

### 4. 進階演算法

#### Monte Carlo 模擬
隨機打亂交易順序 N 次 (預設 500)，評估策略穩健度。
```bash
python3 -m stock_analyzer.main montecarlo --preset volatile --strategy macd --n 1000
```
輸出：
- 最終資金分佈 (5%/25%/50%/75%/95% 百分位)
- 獲利機率 / 破產機率 (本金腰斬)
- 最大回撤分佈
- 信賴帶圖表

#### Walk-Forward 分析
滾動視窗訓練→樣本外驗證，防止過擬合。
```bash
python3 -m stock_analyzer.main walkforward --preset uptrend --strategy golden_cross --windows 5
```
輸出：
- 每個窗口：訓練夏普 → OOS 報酬/夏普/勝率
- 最佳化參數 vs 樣本外表現
- 累計 OOS 權益曲線

#### Grid Search 參數最佳化
窮舉搜尋策略最佳參數組合。
```bash
python3 -m stock_analyzer.main optimize --strategy bollinger --rank-by sharpe
```
輸出：
- 測試組合數
- Top 10 參數排名 (報酬/夏普/Sortino/勝率/回撤)
- 最佳參數建議

#### 回撤恢復分析
追蹤每次回撤的深度、時長、恢復期。
- 水下曲線 (% below peak)
- 每次回撤事件明細
- 平均恢復時間

### 5. 風險管理

| 功能 | 說明 |
|------|------|
| Kelly Criterion | 根據勝率和盈虧比計算最佳倉位 (使用半 Kelly) |
| Fixed Fraction | 固定風險金額計算股數 |
| ATR Position Sizing | 根據波動率計算倉位 |
| VaR (Value at Risk) | 95% 信心水準風險值 |
| 回撤監控 | 即時監控回撤是否超過限制 |
| 風報比計算 | 進場前評估 Risk/Reward |

### 6. 策略評分系統 (A-F 評級)

| 指標 | 權重 | 說明 |
|------|------|------|
| 夏普比率 | 25% | 風險調整後報酬 |
| 獲利因子 | 20% | 總獲利 / 總虧損 |
| 勝率 | 20% | 獲利交易佔比 |
| 回撤控制 | 20% | 最大回撤越小越好 |
| 穩定性 | 15% | 月報酬變異係數 |

| 等級 | 分數 | 建議 |
|------|------|------|
| A | >= 80 | 策略優異，建議實盤使用 |
| B | >= 65 | 表現良好，可適度配置 |
| C | >= 50 | 表現中等，建議小部位測試 |
| D | >= 35 | 表現不佳，需要優化 |
| F | < 35 | 不建議使用 |

---

## CLI 命令大全

```bash
# ── 基本分析 ──
python3 -m stock_analyzer.main analyze --preset uptrend
python3 -m stock_analyzer.main analyze --symbol AAPL
python3 -m stock_analyzer.main signals --strategy macd --preset volatile

# ── 回測 ──
python3 -m stock_analyzer.main backtest --strategy bollinger --capital 500000
python3 -m stock_analyzer.main backtest --strategy macd --trailing-stop 0.05 --allow-short
python3 -m stock_analyzer.main backtest --strategy ema_cross --max-positions 3 --stop-loss 0.08 --take-profit 0.15

# ── 進階演算法 ──
python3 -m stock_analyzer.main montecarlo --strategy macd --n 1000
python3 -m stock_analyzer.main walkforward --strategy golden_cross --windows 5
python3 -m stock_analyzer.main optimize --strategy bollinger --rank-by sharpe

# ── 完整報告 ──
python3 -m stock_analyzer.main full --preset uptrend --capital 1000000

# ── 匯出 ──
python3 -m stock_analyzer.main export --strategy bollinger --preset uptrend

# ── 網頁儀表板 ──
python3 -m stock_analyzer.main server --port 8080

# ── JSON 輸出 (供程式串接) ──
python3 -m stock_analyzer.main json --strategy composite --preset volatile
```

### 參數說明

| 參數 | 說明 | 範例 |
|------|------|------|
| `--preset` | 模擬資料集 | `uptrend` / `volatile` / `bearish` / `default` |
| `--symbol` | Yahoo Finance 股票代碼 | `AAPL` / `TSLA` / `2330.TW` |
| `--csv` | 本地 CSV 檔案路徑 | `./data/stock.csv` |
| `--strategy` | 交易策略 | 見策略表 |
| `--capital` | 初始資金 | `1000000` |
| `--stop-loss` | 停損百分比 | `0.05` (5%) |
| `--take-profit` | 停利百分比 | `0.10` (10%) |
| `--trailing-stop` | 移動停損百分比 | `0.05` (5%) |
| `--max-positions` | 加碼層數 | `3` |
| `--allow-short` | 允許做空 | 無需值 |
| `--rank-by` | 排序依據 (optimize) | `sharpe` / `return` / `sortino` / `win_rate` |
| `--windows` | WF 窗口數 | `5` |
| `--n` | MC 模擬次數 | `500` |

---

## 網頁儀表板

啟動 `python3 -m stock_analyzer.main server --port 8080` 後開啟 http://localhost:8080

### 控制列
- 資料來源選擇 (預設模擬 / 上漲 / 高波動 / 下跌 / 自訂股票代碼)
- 策略選擇 (9 種)
- 初始資金設定
- 停損 % / 停利 % / 移動停損 %
- 加碼層數 / 做空開關
- 自動更新 (10s / 30s / 60s)

### 圖表與卡片
| 卡片 | 說明 |
|------|------|
| 價格走勢 | K 線 + SMA + 布林帶 + 停損停利區間 + 移動停損線 + 買賣標記 |
| 綜合評分 | A-F 等級圓圈 + 五維雷達圖 + 建議文字 |
| 策略擂台 | 全策略同台比較表，最佳欄位金色標示 |
| 回測績效 | 報酬率 / 年化 / 勝率 / 獲利因子 / 連勝連敗 / 期望值 |
| 風險指標 | 夏普 / Sortino / 最大回撤 / Calmar + 進度條 |
| 權益曲線 | 策略 vs 買入持有對比 |
| RSI & MACD | 雙軸顯示 RSI(14) + MACD + Signal |
| 成交量 & OBV | 量能柱狀圖 + OBV 趨勢線 |
| 交易訊號 | 最近 25 筆訊號明細 (買/賣/強度/原因) |
| 交易紀錄 | 完整交易表 (方向/進出場/停損停利/原因/損益) |

### 進階分析按鈕
| 按鈕 | 功能 |
|------|------|
| 🎲 Monte Carlo | 500 次模擬 → 分佈直方圖 + 信賴帶圖 + 獲利/破產機率 |
| 📐 Walk-Forward | 5 窗口滾動驗證 → 每窗口績效表 + OOS 權益曲線 |
| 🔍 Grid Search | 參數窮舉 → Top 10 排名表 |

---

## API 端點

| 端點 | 說明 |
|------|------|
| `GET /api/analyze` | 完整分析 (指標 + 訊號 + 回測 + 回撤) |
| `GET /api/score` | 策略 A-F 評分 |
| `GET /api/compare` | 多策略比較 |
| `GET /api/montecarlo` | Monte Carlo 模擬 |
| `GET /api/walkforward` | Walk-Forward 分析 |
| `GET /api/optimize` | Grid Search 最佳化 |
| `GET /api/export` | 交易紀錄 JSON 匯出 |
| `GET /api/strategies` | 可用策略列表 |
| `GET /api/presets` | 可用資料預設列表 |

通用參數: `preset`, `symbol`, `strategy`, `capital`, `stop_loss`, `take_profit`, `trailing_stop`, `max_positions`, `allow_short`

---

## CSV 資料格式

支援匯入自訂 CSV，欄位需包含：
```
date,open,high,low,close,volume
2025-01-02,100.00,102.50,99.50,101.00,5000000
```

使用方式：
```bash
python3 -m stock_analyzer.main backtest --csv ./my_stock.csv --strategy macd
```
