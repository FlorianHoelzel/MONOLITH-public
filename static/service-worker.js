const CACHE_VERSION = "monolith-public-shell-v3";
const SHELL_ASSETS = [
  "/",
  "/static/style.css?v=20261009-public-neutral-2",
  "/static/app.js?v=20261009-public-neutral-2",
  "/static/fonts/manrope/Manrope-Latin-Variable.woff2",
  "/static/fonts/manrope/Manrope-LatinExt-Variable.woff2",
  "/static/manifest.webmanifest",
  "/static/monolith-logo.png",
  "/static/icons/icon-180.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-maskable-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then(cache => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches
      .keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key !== CACHE_VERSION)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;

  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  if (
    url.origin === self.location.origin
    && url.pathname.startsWith("/api/")
  ) {
    return;
  }

  if (request.mode === "navigate") {
    const navigationCacheKey = url.pathname;

    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          return caches
            .open(CACHE_VERSION)
            .then(cache => cache.put(navigationCacheKey, copy))
            .then(() => response);
        })
        .catch(async () => (
          (await caches.match(navigationCacheKey))
          || caches.match("/")
        ))
    );
    return;
  }

  const cacheableAsset =
    url.origin === self.location.origin
    || url.hostname === "cdn.jsdelivr.net";

  if (!cacheableAsset) {
    return;
  }

  const networkResponse = fetch(request)
    .then(response => {
      if (response.ok || response.type === "opaque") {
        const copy = response.clone();
        return caches
          .open(CACHE_VERSION)
          .then(cache => cache.put(request, copy))
          .then(() => response);
      }
      return response;
    });

  event.waitUntil(
    networkResponse.catch(() => undefined)
  );

  event.respondWith(
    caches
      .match(request)
      .then(cachedResponse => cachedResponse || networkResponse)
  );
});

self.addEventListener("push", event => {
  let payload = {};

  try {
    payload = event.data
      ? event.data.json()
      : {};
  } catch (error) {
    payload = {
      body: event.data?.text() || "Neue MONOLITH-Mitteilung"
    };
  }

  const notification = payload.notification || payload;
  const title = notification.title || "MONOLITH";
  const options = {
    body: notification.body || "Neue Mitteilung",
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    tag: notification.tag || payload.tag || "monolith",
    renotify: false,
    data: {
      url: notification.navigate || payload.url || "/",
      messageId: payload.message_id || null
    }
  };

  event.waitUntil(
    self.registration.showNotification(
      title,
      options
    )
  );
});

self.addEventListener("pushsubscriptionchange", event => {
  event.waitUntil((async () => {
    let subscription = event.newSubscription;

    // Explicitly unsubscribing must not silently turn notifications back on.
    if (!subscription && !event.oldSubscription) {
      return;
    }

    if (!subscription) {
      subscription = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: event.oldSubscription.options.applicationServerKey
      });
    }

    const response = await fetch("/api/push/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        ...subscription.toJSON(),
        previous_endpoint: event.oldSubscription?.endpoint
      })
    });
    if (!response.ok) {
      throw new Error("Erneuertes Push-Abonnement konnte nicht gespeichert werden");
    }
  })());
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const targetUrl = new URL(
    event.notification.data?.url || "/",
    self.location.origin
  ).href;

  event.waitUntil(
    self.clients
      .matchAll({
        type: "window",
        includeUncontrolled: true
      })
      .then(windowClients => {
        const existingClient = windowClients.find(
          client => client.url.startsWith(
            self.location.origin
          )
        );

        if (existingClient) {
          existingClient.navigate(targetUrl);
          return existingClient.focus();
        }

        return self.clients.openWindow(targetUrl);
      })
  );
});
