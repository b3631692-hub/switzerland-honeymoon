// ============================================================
// Gmail Organizer  (Google Apps Script 版)
// 1. 把廣告/促銷信歸檔
// 2. 把長期未讀的舊信丟垃圾桶
// 3. 把信用卡帳單 PDF 存到 Google Drive (依年份/銀行整理)
//
// 使用方式: 編輯下面 CONFIG -> 在編輯器選函式 -> 點「執行」
// 第一次執行 Google 會要求授權, 同意後就能跑
// ============================================================

const CONFIG = {
  // 第一次跑請保持 true (只列出會做什麼, 不會真的動信件)
  // 確認沒問題, 改成 false 才會實際執行
  DRY_RUN: true,

  // === 廣告信歸檔 (執行 archivePromos) ===
  archivePromos: {
    enabled: true,
    // 多久之前的信才處理 (避免剛收到的還沒看就被歸檔)
    olderThanDays: 3,
    // 是否抓 Gmail 內建的「促銷內容」分類
    useCategoryPromotions: true,
    // 主旨或寄件人含這些字 -> 視為廣告
    extraKeywords: ['電子報', 'newsletter', '優惠', '折扣', 'unsubscribe'],
    // 歸檔同時標記為已讀
    markAsRead: true,
    // 每次最多處理幾封 (Apps Script 有 6 分鐘執行限制)
    maxThreads: 500,
  },

  // === 老舊未讀信清理 (執行 cleanupOldUnread) ===
  cleanupOld: {
    enabled: true,
    // 多久沒互動的信才算「舊」
    olderThanDays: 365,
    // 只清未讀 (true) 或所有舊信 (false)
    unreadOnly: true,
    // 排除這些 label (即使符合條件也不動)
    excludeLabels: ['IMPORTANT'],
    // 排除這些寄件人 (永遠不刪)
    excludeSenders: [
      // 'boss@company.com',
      // 'mom@example.com',
    ],
    // 'trash' (丟垃圾桶, 30天後自動清, 可救回) 或 'delete' (永久刪除, 危險)
    action: 'trash',
    maxThreads: 500,
  },

  // === 信用卡帳單下載 (執行 downloadStatements) ===
  statements: {
    enabled: true,
    // Drive 上的根資料夾名稱 (沒有會自動建立)
    driveFolderName: 'Gmail 信用卡帳單',
    // 往回找幾天
    lookbackDays: 730,
    // 寄件人 domain (台灣常見銀行 + 主要國際發卡行)
    issuerDomains: [
      'cathaybk.com.tw', 'cathayholdings.com',
      'ctbcbank.com',
      'esunbank.com.tw',
      'taishinbank.com.tw',
      'fubon.com',
      'sinopac.com',
      'hsbc.com.tw',
      'citibank.com.tw',
      'sc.com', 'standardchartered.com.tw',
      'americanexpress.com', 'aexp.com',
      'firstbank.com.tw',
      'megabank.com.tw',
      'bot.com.tw',
      'landbank.com.tw',
      'tcb-bank.com.tw',
      'scsb.com.tw',
      'kgibank.com',
    ],
    // 主旨關鍵字 (任一命中也視為帳單)
    subjectKeywords: ['信用卡', '電子帳單', '對帳單', '繳款通知', 'Statement', 'eStatement', 'e-Bill'],
    // 處理過的信會加上這個 label, 下次跳過 (避免重複下載)
    processedLabel: 'Statements/Downloaded',
    maxThreads: 200,
  },
};

// ============================================================
// 主要進入點
// ============================================================

/** 一鍵跑全部 (在「執行」選單選這個就會三個都做) */
function runAll() {
  if (CONFIG.archivePromos.enabled) archivePromos();
  if (CONFIG.cleanupOld.enabled) cleanupOldUnread();
  if (CONFIG.statements.enabled) downloadStatements();
  Logger.log('=== 全部完成 ===');
}

// ============================================================
// 1. 廣告信歸檔
// ============================================================

function archivePromos() {
  const cfg = CONFIG.archivePromos;
  const query = buildPromoQuery_(cfg);
  Logger.log('[archivePromos] 搜尋: %s', query);

  const threads = GmailApp.search(query, 0, cfg.maxThreads);
  Logger.log('[archivePromos] 找到 %s 個 thread', threads.length);

  preview_(threads, 10);

  if (CONFIG.DRY_RUN) {
    Logger.log('[archivePromos] DRY_RUN, 不執行. 把 CONFIG.DRY_RUN 改為 false 才會動.');
    return;
  }

  // GmailApp 提供批次操作: 一次最多 100 個 thread
  for (const chunk of chunk_(threads, 100)) {
    GmailApp.moveThreadsToArchive(chunk);
    if (cfg.markAsRead) GmailApp.markThreadsRead(chunk);
  }
  Logger.log('[archivePromos] 完成: %s 個 thread 已歸檔', threads.length);
}

function buildPromoQuery_(cfg) {
  const parts = ['in:inbox'];
  if (cfg.olderThanDays > 0) parts.push('older_than:' + cfg.olderThanDays + 'd');

  const orParts = [];
  if (cfg.useCategoryPromotions) orParts.push('category:promotions');
  for (const kw of cfg.extraKeywords || []) {
    orParts.push('(subject:"' + kw + '" OR from:"' + kw + '")');
  }
  if (orParts.length) parts.push('(' + orParts.join(' OR ') + ')');

  return parts.join(' ');
}

// ============================================================
// 2. 清理老舊未讀信
// ============================================================

function cleanupOldUnread() {
  const cfg = CONFIG.cleanupOld;
  const query = buildCleanupQuery_(cfg);
  Logger.log('[cleanupOld] 搜尋: %s', query);

  const threads = GmailApp.search(query, 0, cfg.maxThreads);
  Logger.log('[cleanupOld] 找到 %s 個 thread', threads.length);

  // 統計一下來源網域, 給使用者看哪些寄件人在塞信箱
  const domains = {};
  for (const t of threads) {
    const from = t.getMessages()[0].getFrom();
    const m = from.match(/@([^>\s]+)/);
    const d = m ? m[1].toLowerCase().replace(/>$/, '') : from;
    domains[d] = (domains[d] || 0) + 1;
  }
  const top = Object.entries(domains).sort((a, b) => b[1] - a[1]).slice(0, 15);
  Logger.log('[cleanupOld] 寄件人 domain 統計:');
  for (const [d, c] of top) Logger.log('  %s  %s', String(c).padStart(5), d);

  preview_(threads, 10);

  if (CONFIG.DRY_RUN) {
    Logger.log('[cleanupOld] DRY_RUN, 不執行.');
    return;
  }

  for (const chunk of chunk_(threads, 100)) {
    if (cfg.action === 'delete') {
      // 永久刪除沒有 batch API, 一個個來
      for (const t of chunk) t.moveToTrash();  // 先進垃圾桶
      // (若要真的永久刪, 需要 Advanced Gmail API, 預設不啟用)
    } else {
      GmailApp.moveThreadsToTrash(chunk);
    }
  }
  Logger.log('[cleanupOld] 完成: %s 個 thread 已 %s', threads.length, cfg.action);
}

function buildCleanupQuery_(cfg) {
  const parts = ['older_than:' + cfg.olderThanDays + 'd'];
  if (cfg.unreadOnly) parts.push('is:unread');
  parts.push('-in:trash', '-in:drafts', '-in:sent');
  parts.push('-is:starred');
  for (const lbl of cfg.excludeLabels || []) parts.push('-label:' + lbl);
  for (const s of cfg.excludeSenders || []) parts.push('-from:"' + s + '"');
  return parts.join(' ');
}

// ============================================================
// 3. 信用卡帳單下載到 Drive
// ============================================================

function downloadStatements() {
  const cfg = CONFIG.statements;
  const query = buildStatementsQuery_(cfg);
  Logger.log('[statements] 搜尋: %s', query);

  const threads = GmailApp.search(query, 0, cfg.maxThreads);
  Logger.log('[statements] 找到 %s 個 thread', threads.length);

  if (!threads.length) return;

  let rootFolder = null;
  let label = null;
  if (!CONFIG.DRY_RUN) {
    rootFolder = getOrCreateFolder_(cfg.driveFolderName);
    label = ensureLabel_(cfg.processedLabel);
  }

  let downloaded = 0;
  let skipped = 0;
  let noPdf = 0;
  let threadIdx = 0;

  for (const thread of threads) {
    threadIdx++;
    for (const msg of thread.getMessages()) {
      const attachments = msg.getAttachments({includeInlineImages: false});
      const pdfs = attachments.filter(a =>
        a.getContentType() === 'application/pdf' ||
        a.getName().toLowerCase().endsWith('.pdf')
      );

      const from = msg.getFrom();
      const subject = msg.getSubject();
      const date = msg.getDate();
      const issuer = issuerFromSender_(from, cfg.issuerDomains);
      const year = String(date.getFullYear());
      const dateStr = Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy-MM-dd');

      if (!pdfs.length) {
        noPdf++;
        Logger.log('  [%s/%s] (無 PDF) %s | %s', threadIdx, threads.length, issuer, subject.substring(0, 50));
        continue;
      }

      for (const pdf of pdfs) {
        const safeName = dateStr + '_' + sanitize_(pdf.getName());
        if (CONFIG.DRY_RUN) {
          Logger.log('  [%s/%s] (dry-run) %s/%s/%s', threadIdx, threads.length, year, issuer, safeName);
          continue;
        }

        const yearFolder = getOrCreateSubfolder_(rootFolder, year);
        const issuerFolder = getOrCreateSubfolder_(yearFolder, issuer);

        // 跳過已存在的同名檔
        const existing = issuerFolder.getFilesByName(safeName);
        if (existing.hasNext()) {
          skipped++;
          continue;
        }
        issuerFolder.createFile(pdf.copyBlob().setName(safeName));
        downloaded++;
        Logger.log('  [%s/%s] 下載 -> %s/%s/%s', threadIdx, threads.length, year, issuer, safeName);
      }
    }

    if (label && !CONFIG.DRY_RUN) thread.addLabel(label);
  }

  Logger.log('[statements] 統計: 下載 %s / 已存在跳過 %s / 無 PDF %s / 總 thread %s',
             downloaded, skipped, noPdf, threads.length);

  if (CONFIG.DRY_RUN) {
    Logger.log('[statements] DRY_RUN, 沒有實際下載.');
  }
}

function buildStatementsQuery_(cfg) {
  const parts = ['has:attachment', 'newer_than:' + cfg.lookbackDays + 'd'];
  // 排除已處理 (label 可能還沒建, 用 -label: 即使不存在也不會報錯)
  if (cfg.processedLabel) parts.push('-label:"' + cfg.processedLabel + '"');

  const orParts = [];
  for (const d of cfg.issuerDomains || []) orParts.push('from:' + d);
  for (const kw of cfg.subjectKeywords || []) orParts.push('subject:"' + kw + '"');
  if (orParts.length) parts.push('(' + orParts.join(' OR ') + ')');

  return parts.join(' ');
}

function issuerFromSender_(from, knownDomains) {
  const m = from.match(/@([^>\s]+)/);
  if (!m) return 'unknown';
  const domain = m[1].toLowerCase().replace(/>$/, '');
  for (const known of knownDomains) {
    if (domain.indexOf(known) !== -1) return known.split('.')[0];
  }
  return domain.split('.')[0];
}

function sanitize_(name) {
  return name.replace(/[\\/:*?"<>|]+/g, '_').replace(/_+/g, '_');
}

// ============================================================
// 工具函式
// ============================================================

function getOrCreateFolder_(name) {
  const root = DriveApp.getRootFolder();
  const it = root.getFoldersByName(name);
  return it.hasNext() ? it.next() : root.createFolder(name);
}

function getOrCreateSubfolder_(parent, name) {
  const it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}

function ensureLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

function chunk_(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

function preview_(threads, n) {
  Logger.log('前 %s 個 thread 預覽:', Math.min(n, threads.length));
  for (let i = 0; i < Math.min(n, threads.length); i++) {
    const m = threads[i].getMessages()[0];
    Logger.log('  - [%s] %s | %s',
      Utilities.formatDate(m.getDate(), Session.getScriptTimeZone(), 'yyyy-MM-dd'),
      m.getFrom().substring(0, 40),
      m.getSubject().substring(0, 50));
  }
  if (threads.length > n) Logger.log('  ... 還有 %s 個', threads.length - n);
}
