# Gmail Organizer (Apps Script 版)

不用裝 Python、不用 Google Cloud Console、不用任何指令列工具。
整個流程都在瀏覽器跑，10 分鐘搞定。

## 設定步驟

### 1. 打開 Apps Script 編輯器

到 https://script.google.com/ → 點左上「**新增專案**」

### 2. 把 `Code.gs` 整份貼進去

- 左側檔案列表 → 點 `Code.gs` → 把預設的 `function myFunction()...` **全部刪掉**
- 把這個資料夾裡的 [Code.gs](./Code.gs) 全部內容貼進去
- 上方專案名稱（預設「無標題的專案」）可以改成 `Gmail Organizer`
- Ctrl + S 存檔

### 3. 編輯 CONFIG

檔案最上面有個 `CONFIG = {...}`，重點：

- `DRY_RUN: true` — **第一次跑請保持 true**，會印出會處理什麼但不實際動
- `cleanupOld.excludeSenders` — 加上重要寄件人，保護不被誤刪（例如老闆、家人）
- `cleanupOld.olderThanDays` — 多久沒互動算「舊」（預設 365 天）
- `statements.driveFolderName` — 帳單會存到 Drive 的這個資料夾（預設「Gmail 信用卡帳單」）

### 4. 第一次執行 + 授權

1. 上方函式選單選 **`archivePromos`**（或 `runAll` 跑全部）
2. 點 **▶ 執行**
3. 跳出「需要授權」→ **檢閱權限** → 選你的 Google 帳號
4. 看到「Google 尚未驗證這個應用程式」→ 點 **進階** → 點 **前往 [專案名稱]（不安全）**
   - 這警告是因為你的 script 是給自己用的、沒送 Google 審核。你授權給的是**你自己寫的程式**，安全沒問題。
5. 點 **允許**
6. 回到編輯器底下會看到「執行紀錄」，印出搜尋條件和找到的信件

### 5. 確認 dry-run 結果沒問題

執行紀錄會印出：
- 用什麼條件搜尋
- 找到幾封信
- 前 10 封的寄件人/主旨預覽
- （清理舊信時）寄件人 domain 統計

如果名單看起來合理，把 `CONFIG.DRY_RUN` 改成 `false`，再執行一次就會實際處理。

### 6. （選用）設定每天自動執行

1. 左側選單 → **觸發條件**（時鐘圖示）
2. 右下角 **新增觸發條件**
3. 選擇函式：`runAll`（或單獨某個）
4. 活動來源：**時間驅動**
5. 觸發頻率：建議 **日計時器** → 凌晨 1-2 點
6. 儲存

之後每天會自動跑，新的廣告會自動歸檔、新的帳單會自動進 Drive。

## 三個函式

| 函式 | 做什麼 | 預設條件 |
|------|--------|---------|
| `archivePromos` | 廣告/促銷信從收件匣歸檔 | 3 天前的促銷分類 + 含「電子報、優惠、unsubscribe」等關鍵字 |
| `cleanupOldUnread` | 老舊未讀信丟垃圾桶 | 365 天沒互動、未讀、非星標、非 IMPORTANT |
| `downloadStatements` | 信用卡帳單 PDF 存 Drive | 730 天內、寄件人是 18 家銀行、含「信用卡/帳單」關鍵字 |
| `runAll` | 一次跑全部 | — |

## 信用卡帳單在 Drive 怎麼整理

```
我的雲端硬碟/
└── Gmail 信用卡帳單/
    ├── 2024/
    │   ├── cathaybk/
    │   │   ├── 2024-01-15_電子帳單.pdf
    │   │   └── 2024-02-15_電子帳單.pdf
    │   ├── ctbcbank/
    │   └── esunbank/
    └── 2025/
        └── ...
```

下載過的信會被加上 `Statements/Downloaded` label，再跑就會跳過——所以可以放心設定每日自動執行，不會重複下載。

## PDF 解密

Apps Script **沒辦法解密 PDF**（沒有 qpdf 之類的函式庫）。
台灣銀行的帳單通常用身分證/生日加密，要解密的話有兩個選擇：

1. **手動**：從 Drive 下載 PDF → 用 Adobe Acrobat / 預覽程式輸入密碼開啟 → 另存新檔
2. **批次**：用本機的 Python 工具（同一個 repo 的 `gmail-organizer/` 上層資料夾）
   - 只跑 `decrypt-statements` 指令，不用 Gmail 授權
   - 先把 Drive 同步到本機（Google Drive Desktop 客戶端），跑完再同步回去

## 常見問題

**Q: 執行到一半超過 6 分鐘被中斷？**
A: Apps Script 單次最多 6 分鐘。把 CONFIG 裡的 `maxThreads` 調小（例如 100），多跑幾次。觸發條件每天會自動處理新進來的少量信，不會有這問題。

**Q: 想換 Drive 存放位置？**
A: 改 `CONFIG.statements.driveFolderName`，下次執行會在你雲端硬碟根目錄建新資料夾。如果想放在某個既有資料夾下面，可以把原資料夾搬進去就好。

**Q: 改完設定怎麼重新跑 dry-run？**
A: 帳單下載的部分，因為信件已經被加上 `Statements/Downloaded` label 會被跳過。想重新測，到 Gmail 設定 → 標籤 → 把這個 label 刪掉，或在 query 裡暫時拿掉 `-label:` 那段。

**Q: 想撤銷授權？**
A: https://myaccount.google.com/permissions → 找你的專案 → 移除存取權。
