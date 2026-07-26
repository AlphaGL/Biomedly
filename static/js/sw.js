/* Biomedly service worker — "offline-lite".
 *
 * Honest scope: this does NOT make the AI assistant work offline (it needs
 * a live network call, always will). What it does:
 *   - The app shell (CSS/JS/manifest) loads instantly and works offline
 *     once visited once.
 *   - Any page you've actually opened (an asset, a manual link, a past
 *     analysis) is cached and reopens offline — useful in a signal-dead
 *     equipment room when you want to re-read something you already saw.
 *   - A friendly offline page instead of the browser's default "no
 *     internet" error for anything never visited.
 */
const CACHE = "biomedly-v1";
const APP_SHELL = [
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/manifest.webmanifest",
  "/static/offline.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // never cache POST (e.g. api/analyze)

  const url = new URL(req.url);

  // Static assets: cache-first (they're fingerprint-free here, so a short
  // network re-check on each deploy is an acceptable tradeoff for simplicity).
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((res) => {
        const clone = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, clone));
        return res;
      }))
    );
    return;
  }

  // Never intercept the AI/API endpoints — they must always hit the network
  // (or fail loudly), not silently serve stale cached JSON.
  if (url.pathname.startsWith("/api/")) return;

  // Page navigations: network-first, falling back to whatever was cached
  // for that exact URL, then the offline page as a last resort.
  event.respondWith(
    fetch(req)
      .then((res) => {
        const clone = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, clone));
        return res;
      })
      .catch(() =>
        caches.match(req).then((cached) => cached || caches.match("/static/offline.html"))
      )
  );
});
