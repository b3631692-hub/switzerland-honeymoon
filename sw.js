/* Switzerland Honeymoon 2026 — Service Worker */
const CACHE = 'honeymoon-v25';
const CORE = [
  '/switzerland-honeymoon/',
  '/switzerland-honeymoon/index.html',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => {
      return Promise.allSettled(CORE.map(url => c.add(url).catch(() => {})));
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(ks =>
      Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = e.request.url;
  // Always fetch fresh for weather, exchange rate and tile APIs
  if (url.includes('open-meteo.com') || url.includes('frankfurter.app') || url.includes('basemaps.cartocdn') || url.includes('tile.openstreetmap')) return;

  e.respondWith(
    caches.match(e.request).then(cached => {
      const network = fetch(e.request).then(res => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => cached || new Response('Offline', { status: 503 }));
      // Network-first for all resources; fall back to cache when offline
      return network;
    })
  );
});
