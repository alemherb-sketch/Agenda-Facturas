const CACHE = "agenda-facturas-v12";
const ASSETS = [
  "/",
  "/static/css/app.css?v=12",
  "/static/js/api.js?v=12",
  "/static/js/app.js?v=12",
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
  if (request.url.includes("/sw.js")) return;

  const url = new URL(request.url);
  const isAppShell =
    url.pathname === "/" ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".html");

  // CSS/JS/HTML: red primero para no quedar con estilos viejos en el móvil
  if (isAppShell) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200 && request.url.startsWith(self.location.origin)) {
            const clone = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

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

  const tag = `af-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const title = data.title || "Agenda Facturas";
  const body = data.body || "Tienes un recordatorio";
  const url = data.url || "/#/recordatorios";

  event.waitUntil(
    (async () => {
      // Avisa a pestañas abiertas (PC/móvil) para sonido + toast visible
      const list = await clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of list) {
        client.postMessage({
          type: "AF_PUSH",
          title,
          body,
          url,
        });
      }

      await self.registration.showNotification(title, {
        body,
        icon: "/static/icons/icon-192.png",
        badge: "/static/icons/icon-192.png",
        image: undefined,
        tag,
        renotify: true,
        silent: false,
        requireInteraction: true,
        vibrate: [300, 120, 300, 120, 500],
        timestamp: Date.now(),
        data: { url },
        actions: [
          { action: "open", title: "Abrir" },
          { action: "dismiss", title: "Cerrar" },
        ],
      });
    })()
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
