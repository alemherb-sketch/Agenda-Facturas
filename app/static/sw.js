const CACHE = "agenda-facturas-v4";
const ASSETS = [
  "/",
  "/static/css/app.css",
  "/static/js/api.js?v=4",
  "/static/js/app.js?v=4",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS).catch(() => undefined)));
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
  const { request } = event;
  if (request.method !== "GET") return;
  if (request.url.includes("/api/")) return;
  // No cachear el service worker ni el HTML principal de forma agresiva
  if (request.url.includes("/sw.js")) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const fetched = fetch(request)
        .then((response) => {
          if (response && response.status === 200 && request.url.startsWith(self.location.origin)) {
            const clone = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => cached);
      return cached || fetched;
    })
  );
});

self.addEventListener("push", (event) => {
  let data = {
    title: "Agenda Facturas",
    body: "Tienes un recordatorio pendiente",
    url: "/#/recordatorios",
  };
  try {
    if (event.data) {
      const parsed = event.data.json();
      data = { ...data, ...parsed };
    }
  } catch (_) {
    try {
      if (event.data) data.body = event.data.text();
    } catch (__) {
      /* ignore */
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title || "Agenda Facturas", {
      body: data.body || "Tienes un recordatorio",
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
      tag: data.tag || `af-${Date.now()}`,
      renotify: true,
      requireInteraction: true,
      vibrate: [200, 100, 200],
      data: { url: data.url || "/#/recordatorios" },
      actions: [
        { action: "open", title: "Abrir" },
        { action: "dismiss", title: "Cerrar" },
      ],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "dismiss") return;

  const target = event.notification.data?.url || "/#/recordatorios";
  const absolute = new URL(target, self.location.origin).href;

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          client.focus();
          if ("navigate" in client) client.navigate(absolute);
          return;
        }
      }
      if (clients.openWindow) return clients.openWindow(absolute);
    })
  );
});
