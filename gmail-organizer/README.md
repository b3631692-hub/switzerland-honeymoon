# Gmail Organizer

幫你整理 Gmail 的小工具，做三件事：

1. **`archive-promos`** — 把廣告/促銷信從收件匣歸檔（不刪除，只是離開收件匣）
2. **`cleanup-old`** — 把長時間沒互動的未讀信丟到垃圾桶（30 天後自動清掉，期間可救回）
3. **`download-statements`** — 搜尋信用卡帳單，下載 PDF 附件、依年份／發卡銀行分類，並產生一份 `index.csv` 給後續分析
4. **`decrypt-statements`** — 批次解開上一步下載的加密 PDF（台灣銀行帳單常用身分證/生日加密）

> ⚠️ 這個工具會在你自己的電腦上執行，需要你自己到 Google Cloud Console 開一個 OAuth client。Google 不允許第三方拿到你 Gmail 的存取權，這是正常設計。

---

## 一次性設定

### 1. 安裝套件

```bash
cd gmail-organizer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 到 Google Cloud Console 建立 OAuth client

1. 前往 https://console.cloud.google.com/
2. 建立一個新專案（隨便取名，例如 `my-gmail-organizer`）
3. 左側選單 → **APIs & Services → Library** → 搜尋 **Gmail API** → 點 **Enable**
4. 左側選單 → **APIs & Services → OAuth consent screen**
   - User Type 選 **External**
   - App name 隨便填、Support email 填自己
   - Scopes 步驟可以不加（程式碼會自己要）
   - **Test users** 加上你自己的 Gmail（不加會無法授權）
5. 左側選單 → **APIs & Services → Credentials**
   - **Create Credentials → OAuth client ID**
   - Application type 選 **Desktop app**
   - 建立後下載 JSON，改名為 `credentials.json`，放到 `gmail-organizer/` 資料夾

### 3. 複製設定檔

```bash
cp config.example.yaml config.yaml
# 編輯 config.yaml 調整關鍵字、保護名單、時間範圍
```

### 4. 第一次授權

```bash
python -m gmail_organizer.cli auth
```

會打開瀏覽器要你登入並授權，授權後產生 `token.json`，之後就不用再做了。

---

## 使用方式

**所有指令預設都是 `dry-run`**，只列出會動到的信件、不會實際更動。確認 OK 再加 `--apply`。

### 歸檔廣告信

```bash
# 先看看會抓到哪些
python -m gmail_organizer.cli archive-promos

# 只試 50 封
python -m gmail_organizer.cli archive-promos --limit 50 --apply

# 確認沒問題就全做
python -m gmail_organizer.cli archive-promos --apply
```

### 清理舊未讀信

```bash
python -m gmail_organizer.cli cleanup-old             # dry-run
python -m gmail_organizer.cli cleanup-old --apply     # 丟垃圾桶
```

`cleanup_old.action` 預設 `trash`（垃圾桶 30 天保留），改成 `delete` 才會永久刪除。建議**永遠保留 `trash`**。

### 下載信用卡帳單

```bash
# 看會抓到哪些信、會下載哪些檔名 (不會真的下載)
python -m gmail_organizer.cli download-statements

# 開始下載
python -m gmail_organizer.cli download-statements --apply
```

下載結構：

```
statements/
├── index.csv               ← 所有帳單的索引，可丟進 Excel/pandas
├── 2024/
│   ├── cathaybk/
│   │   ├── 2024-01-15_信用卡帳單.pdf
│   │   └── 2024-02-15_信用卡帳單.pdf
│   ├── ctbcbank/
│   └── esunbank/
└── 2025/
    └── ...
```

`index.csv` 欄位：`date, issuer, from, subject, filename, message_id`，可以直接：

```python
import pandas as pd
df = pd.read_csv("statements/index.csv")
df.groupby(["issuer", df["date"].str[:7]]).size()
```

### 解密 PDF 帳單

在 `config.yaml` 的 `decrypt` 區段填入候選密碼（身分證、生日 YYYYMMDD、生日 MMDD、卡號末四碼…）。
不同銀行用不同密碼可以填到 `per_issuer`，會優先試該銀行的，再 fallback 到全域清單。

```bash
# 看會解開幾個、用哪組密碼 (不會寫檔)
python -m gmail_organizer.cli decrypt-statements

# 實際輸出到 statements_decrypted/
python -m gmail_organizer.cli decrypt-statements --apply
```

輸出標記：
- `✓` 成功解密（顯示用第幾組密碼，**不顯示密碼本身**）
- `·` 原本就沒加密
- `✗` 試過所有密碼都不行（會在最後列出，方便補密碼）
- `-` 目標檔已存在，跳過（重跑不會重做）
- `!` 讀取/寫入錯誤

> 解密後的 PDF 沒有密碼保護，請放在安全的位置，不要意外上傳/分享。

---

## 安全與隱私

- `credentials.json`、`token.json`、`config.yaml`、`statements/` 都在 `.gitignore`，不會被 commit
- OAuth scope 只用 `gmail.modify`：可以讀、加 label、改狀態、刪除，**但不能改密碼或存取其他 Google 服務**
- 「刪除」預設只是 `trash`（垃圾桶 30 天保留期）
- 想撤銷授權：https://myaccount.google.com/permissions

## 注意事項

- 第一次跑前面三個 Gmail 指令前，**強烈建議先 dry-run 看名單**，特別是 `cleanup-old`。
- 大信箱（10 萬封以上）第一次跑可能要幾分鐘，Gmail API 有 rate limit，工具會自動處理分頁但不會自動 backoff——如果遇到 429 錯誤，等一分鐘再跑。
- `decrypt-statements` 不需要網路、也不會碰 Gmail，純粹在本機跑 `pikepdf`，安裝它需要先有 `qpdf` 系統套件：
  - macOS: `brew install qpdf`
  - Ubuntu/Debian: `sudo apt install qpdf`
  - Windows: 通常 `pip install pikepdf` 會自帶 wheel，不用裝
