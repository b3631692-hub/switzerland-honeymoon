(() => {
  'use strict';
  const views = ['overview', 'plan', 'budget', 'bookings', 'notes', 'options', 'shopping'];
  const panels = views.map(id => document.getElementById(id));
  const tabs = document.querySelector('.daytabs');
  const panel = document.getElementById('day-panel');
  const themeButton = document.getElementById('theme-toggle');
  let selectedDay = 0;
  const esc = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const kind = type => type === '已訂' ? 'confirmed' : (['待選','待確認'].includes(type) ? 'pending' : 'planned');
  function setHash(hash) { if (location.hash !== hash) history.pushState(null, '', hash); }
  function showView(name, scroll = true, writeHash = true) {
    if (!views.includes(name)) name = 'overview';
    panels.forEach(p => p.hidden = p.id !== name);
    document.querySelectorAll('[data-view]').forEach(b => {
      const active = b.dataset.view === name;
      b.classList.toggle('active', active);
      if (active) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current');
    });
    if (writeHash) setHash(name === 'plan' ? `#day-${selectedDay + 1}` : `#${name}`);
    if (scroll) window.scrollTo({top:0, behavior:'auto'});
  }
  function showDay(index, focus = false, writeHash = true) {
    if (!Number.isInteger(index) || index < 0 || index >= TRIP.days.length) return;
    selectedDay = index;
    const day = TRIP.days[index];
    tabs.querySelectorAll('button').forEach((b,i) => { b.setAttribute('aria-selected',String(i === index)); b.tabIndex = i === index ? 0 : -1; });
    panel.setAttribute('aria-labelledby', `day-tab-${index}`);
    panel.innerHTML = `<div class="dayhead"><span class="daynumber" aria-hidden="true">${String(index + 1).padStart(2,'0')}</span><div><h2>${esc(day.title)}</h2><p>${esc(day.subtitle)}</p></div></div><p class="day-distance">${esc(day.distance)}</p><ol class="timeline">${day.events.map(e => `<li class="event"><div class="eventtime">${esc(e.time)}</div><div class="eventbody"><div class="eventtitle"><h3>${esc(e.name)}</h3><span class="tag ${kind(e.type)}">${esc(e.type)}</span></div><p>${esc(e.note)}</p>${e.map ? `<a class="maplink" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(e.map)}" target="_blank" rel="noopener noreferrer" aria-label="在 Google 地圖開啟${esc(e.name)}">開啟地圖</a>` : ''}</div></li>`).join('')}</ol><div class="hotelbar">${index === TRIP.days.length-1 ? '旅程終點' : '今晚住宿'}<strong>${esc(day.hotel)}</strong></div><div class="day-controls" aria-label="切換行程日期"><button type="button" data-step="-1" ${index === 0 ? 'disabled' : ''}>← 前一天</button><button type="button" data-step="1" ${index === TRIP.days.length-1 ? 'disabled' : ''}>下一天 →</button></div>`;
    if (writeHash && !document.getElementById('plan').hidden) setHash(`#day-${index+1}`);
    if (focus) tabs.children[index].focus({preventScroll:true});
  }
  tabs.innerHTML = TRIP.days.map((d,i) => `<button type="button" role="tab" id="day-tab-${i}" aria-controls="day-panel" aria-selected="${i===0}" tabindex="${i===0?0:-1}" data-day="${i}"><span class="date">${esc(d.date)}<small>${esc(d.weekday)}</small></span><span class="area">${esc(d.area)}</span></button>`).join('');
  tabs.addEventListener('click', e => {const b=e.target.closest('[data-day]'); if(b) showDay(Number(b.dataset.day));});
  tabs.addEventListener('keydown', e => {
    if (!['ArrowRight','ArrowLeft','Home','End'].includes(e.key)) return;
    e.preventDefault();
    const count=TRIP.days.length;
    showDay(e.key==='Home'?0:e.key==='End'?count-1:(selectedDay+(e.key==='ArrowRight'?1:count-1))%count,true);
  });
  panel.addEventListener('click', e => {
    const b=e.target.closest('[data-step]'); if(!b || b.disabled) return;
    showDay(selectedDay+Number(b.dataset.step),true);
    tabs.scrollIntoView({block:'nearest',behavior:'auto'});
  });
  document.querySelectorAll('[data-view],[data-open-view]').forEach(b => b.addEventListener('click', e => {e.preventDefault();showView(b.dataset.view||b.dataset.openView);}));
  document.querySelectorAll('[data-overview-day]').forEach(b => b.addEventListener('click', () => {showDay(Number(b.dataset.overviewDay),false,false);showView('plan');}));
  function setTheme(theme) {
    document.documentElement.dataset.theme=theme;
    const dark=theme==='dark';
    themeButton.setAttribute('aria-label',dark?'切換淺色模式':'切換深色模式');
    themeButton.setAttribute('aria-pressed',String(dark));
    document.querySelector('meta[name="theme-color"]').content=dark?'#222c35':'#f8f8f5';
  }
  let theme='light';
  try { theme=localStorage.getItem('okinawa-theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'); } catch {}
  setTheme(theme==='dark'?'dark':'light');
  themeButton.addEventListener('click',()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('okinawa-theme',theme);}catch{}});
  function updateClocks() {
    const now=new Date();
    document.getElementById('clock-taipei').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hour12:false}).format(now);
    document.getElementById('clock-okinawa').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit',hour12:false}).format(now);
    const delta=Date.parse('2026-10-07T14:55:00+08:00')-now.getTime();
    const before=delta>0;
    document.getElementById('countdown-digits').hidden=!before;
    document.getElementById('countdown-digits').style.display=before?'':'none';
    document.getElementById('countdown-label').textContent=before?'距離出發':'OUR ISLAND DAYS';
    if(before){
      const mins=Math.floor(delta/60000);
      document.getElementById('countdown-days').textContent=String(Math.floor(mins/1440)).padStart(2,'0');
      document.getElementById('countdown-hours').textContent=String(Math.floor(mins/60)%24).padStart(2,'0');
      document.getElementById('countdown-minutes').textContent=String(mins%60).padStart(2,'0');
      document.getElementById('countdown').textContent='';
    }else{
      document.getElementById('countdown').textContent=now.getTime()<Date.parse('2026-10-10T18:55:00+08:00')?'旅程進行中 · 好好享受每一天':'旅行回憶，持續收藏。';
    }
  }
  function readHash(scroll=false) {
    const hash=location.hash.slice(1), match=/^day-([1-4])$/.exec(hash);
    showDay(match?Number(match[1])-1:0,false,false);
    showView(match?'plan':views.includes(hash)?hash:'overview',scroll,false);
  }
  window.addEventListener('popstate',()=>readHash(true));
  window.addEventListener('hashchange',()=>readHash(true));
  updateClocks();setInterval(updateClocks,1000);readHash();
})();
