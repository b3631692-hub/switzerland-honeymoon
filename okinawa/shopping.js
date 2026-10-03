(() => {
  'use strict';
  const products = window.SHOPPING.products;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL = value => {try { const url = new URL(value); return url.protocol === 'https:' ? url.href : ''; } catch { return ''; }};
  const link = (url, label) => safeURL(url) ? `<a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : esc(label);
  const key = 'okinawa-shopping-v1';
  const expandedEvidence = new Set();
  let saved = new Set(), category = '全部', savedOnly = false;
  const validIDs = new Set(products.map(p => p.id));
  function storageWarning() { $('shopping-storage').hidden = false; $('shopping-storage').textContent = '瀏覽器無法儲存清單；這次開啟期間仍可使用，重新整理後可能不保留。'; }
  try {const parsed = JSON.parse(localStorage.getItem(key) || '[]'); if (!Array.isArray(parsed)) throw Error('Invalid saved list'); saved = new Set(parsed.filter(id => typeof id === 'string' && validIDs.has(id)));} catch {storageWarning();}
  const categories = ['全部', ...new Set(products.map(p => p.category))];
  $('shopping-filters').innerHTML = categories.map(c => `<button type="button" data-category="${esc(c)}" aria-pressed="${c === category}">${esc(c)}</button>`).join('');
  function card(p, index) {
    const selected = saved.has(p.id);
    return `<article class="shopping-card" aria-labelledby="product-${esc(p.id)}"><div class="shopping-card-top"><span class="shopping-index">${String(index + 1).padStart(2,'0')}</span><span class="tag">${esc(p.category)}</span><button class="shopping-bookmark" type="button" data-save="${esc(p.id)}" aria-pressed="${selected}" aria-label="${selected ? '移出清單' : '加入清單'}：${esc(p.name)}"><span aria-hidden="true">${selected ? '✓' : '+'}</span><span>${selected ? '已收藏' : '想看看'}</span></button></div><p class="shopping-brand">${esc(p.brand)}</p><h3 id="product-${esc(p.id)}">${esc(p.name)}</h3><p class="shopping-model">${esc(p.model)}</p><div class="shopping-price"><strong>${esc(p.price || '價格待店頭確認')}</strong><span>${esc(p.priceNote || '未核實官方售價')}</span></div><p class="shopping-description">${esc(p.why)}</p><dl class="shopping-facts"><dt>先想一下</dt><dd>${esc(p.caution)}</dd><dt>行李考量</dt><dd>${esc(p.portability)}</dd><dt>找貨起點</dt><dd>${p.stores.map(s => link(s.url,s.name)).join("／")}<small>門市現貨未核實</small></dd></dl>${p.power ? `<div class="shopping-power"><b>回台前，先衡量供電與保固</b><p>${esc(p.power)}</p></div>` : ""}<details class="shopping-evidence" data-evidence="${esc(p.id)}" ${expandedEvidence.has(p.id) ? 'open' : ''}><summary>為什麼入選・查看來源</summary><div><p class="shopping-evidence-note">${esc(p.evidenceNote)}</p>${p.reviews.map(r => `<p>${link(r.url,r.label)}<small>評價／回覆：${esc(r.date)} · ${esc(r.kind)}</small><span>${esc(r.summary)}</span></p>`).join('')}${p.officials.map(s => `<p>${link(s.url,s.title)}</p>`).join('')}<p><small>官方資料查核：2026/10/3 · ${esc(p.price ? '價格可能調整' : '未取得可核對售價')}</small></p></div></details></article>`;
  }
  function render() {
    $('shopping-results').querySelectorAll('[data-evidence]').forEach(detail => {detail.open ? expandedEvidence.add(detail.dataset.evidence) : expandedEvidence.delete(detail.dataset.evidence);});
    const q = $('shopping-query').value.trim().toLocaleLowerCase();
    const visible = products.filter(p => (category === '全部' || p.category === category) && (!savedOnly || saved.has(p.id)) && [p.name,p.brand,p.model,p.why,p.category,p.where].join(' ').toLocaleLowerCase().includes(q));
    $('shopping-results').innerHTML = visible.map(p => card(p, products.indexOf(p))).join('');
    $('shopping-empty').hidden = visible.length !== 0;
    $('shopping-empty-hint').textContent = savedOnly && !saved.size ? '按商品右上角的「想看看」，建立自己的旅行清單。' : '試試其他關鍵字，或重設篩選。';
    $('shopping-count').textContent = `${visible.length} 件商品${savedOnly ? ' · 我的清單' : ''}${category !== '全部' ? ' · ' + category : ''}`;
    $('shopping-saved-count').innerHTML = `${saved.size} <small>件想看看</small>`;
    $('shopping-saved-only').setAttribute('aria-pressed', String(savedOnly));
    $('shopping-filters').querySelectorAll('[data-category]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.category === category)));
  }
  $('shopping-query').addEventListener('input', render);
  $('shopping-filters').addEventListener('click', e => {const b = e.target.closest('[data-category]'); if (!b || !categories.includes(b.dataset.category)) return; category = b.dataset.category; render();});
  $('shopping-saved-only').addEventListener('click', () => {savedOnly = !savedOnly; render();});
  $('shopping-results').addEventListener('click', e => {
    const b = e.target.closest('[data-save]'); if (!b || !validIDs.has(b.dataset.save)) return;
    const id = b.dataset.save; saved.has(id) ? saved.delete(id) : saved.add(id);
    try {localStorage.setItem(key, JSON.stringify([...saved]));} catch {storageWarning();}
    render();
    const replacement = $('shopping-results').querySelector(`[data-save="${id}"]`);
    (replacement || $('shopping-saved-only')).focus({preventScroll:true});
  });
  function reset() {category = '全部'; savedOnly = false; $('shopping-query').value = ''; render(); $('shopping-query').focus({preventScroll:true});}
  $('shopping-reset').addEventListener('click', reset);
  $('shopping-empty-reset').addEventListener('click', reset);
  render();
})();
