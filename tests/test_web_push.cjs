const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.resolve(__dirname, "..");

function worker() {
  const events = new Map();
  const shown = [];
  let networkCalls = 0;
  const context = vm.createContext({
    self: {
      addEventListener: (name, handler) => events.set(name, handler),
      registration: {
        showNotification: async (title, options) => shown.push({ title, options })
      }
    },
    fetch: async () => {
      networkCalls += 1;
      throw new Error("MONOLITH is unreachable outside home Wi-Fi");
    }
  });
  vm.runInContext(fs.readFileSync(path.join(projectRoot, "static/service-worker.js"), "utf8"), context);
  return {
    events, shown,
    networkCalls: () => networkCalls,
    push: async payload => {
      let completion;
      events.get("push")({
        data: { json: () => payload },
        waitUntil: promise => { completion = promise; }
      });
      await completion;
    }
  };
}

test("notification display succeeds with no connection to the LAN server", async () => {
  const sw = worker();
  await sw.push({
    web_push: 8030,
    notification: {
      title: "Futterzeit für dein Haustier", body: "Mittagessen ist jetzt dran.",
      navigate: "https://monolith.local/?tab=pet", tag: "lunch-2026-10-04"
    },
    message_id: "pet:2026-10-04:2"
  });
  assert.equal(sw.shown.length, 1);
  assert.equal(sw.shown[0].title, "Futterzeit für dein Haustier");
  assert.equal(sw.shown[0].options.body, "Mittagessen ist jetzt dran.");
  assert.equal(sw.shown[0].options.data.url, "https://monolith.local/?tab=pet");
  assert.equal(sw.shown[0].options.renotify, false);
  assert.equal(sw.networkCalls(), 0);
});

test("old pending payloads still display after service-worker upgrade", async () => {
  const sw = worker();
  await sw.push({ title: "MONOLITH", body: "Test", tag: "old", url: "/?tab=pet" });
  assert.equal(sw.shown.length, 1);
  assert.equal(sw.shown[0].options.body, "Test");
  assert.equal(sw.networkCalls(), 0);
});

function page({ optedOut = false, offline = false, expired = false } = {}) {
  const listeners = new Map();
  const documentListeners = new Map();
  const values = new Map(optedOut ? [["monolith.webpush.enabled", "false"]] : []);
  let saved = 0;
  let created = 0;
  let removed = 0;
  let subscription = { endpoint: "https://push.test/phone", unsubscribe: async () => { removed++; subscription = null; } };
  const button = { dataset: {}, addEventListener: (name, handler) => listeners.set(`button:${name}`, handler) };
  const window = {
    isSecureContext: true, PushManager: {}, Notification: {},
    localStorage: {
      getItem: key => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value)
    },
    addEventListener: (name, handler) => listeners.set(name, handler),
    alert: () => {}
  };
  const context = vm.createContext({
    window,
    document: { visibilityState: "visible", addEventListener: (name, handler) => documentListeners.set(name, handler) },
    navigator: { serviceWorker: { ready: Promise.resolve({ pushManager: { getSubscription: async () => subscription } }) } },
    Notification: { permission: "granted", requestPermission: async () => "granted" },
    console: { warn: () => {}, error: () => {} },
    qs: () => button,
    setPushButtonState: (button, state) => { button.dataset.state = state; },
    sendPushSubscription: async () => { if (offline) throw new Error("offline"); saved++; },
    getPushSubscriptionStatus: async () => { if (offline) throw new Error("offline"); return !expired; },
    createPushSubscription: async (_registration, previousEndpoint) => {
      created++;
      assert.equal(previousEndpoint, expired ? "https://push.test/phone" : undefined);
      subscription = { endpoint: "https://push.test/new" };
      return subscription;
    },
    fetch: async () => ({ ok: true }),
  });
  const source = fs.readFileSync(path.join(projectRoot, "static/app.js"), "utf8");
  const start = source.indexOf("async function setupPushNotifications()");
  const end = source.indexOf("// WEATHER", start);
  assert.ok(start >= 0 && end > start);
  vm.runInContext(source.slice(start, end), context);
  return { context, button, listeners, documentListeners, counts: () => ({ saved, created, removed }) };
}

test("explicitly disabling push is preserved when the app returns to foreground", async () => {
  const p = page();
  await vm.runInContext("setupPushNotifications()", p.context);
  await p.listeners.get("button:click")();
  p.documentListeners.get("visibilitychange")();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(p.counts().removed, 1);
  assert.equal(p.counts().created, 0);
  assert.equal(p.button.dataset.state, "inactive");
});

test("opt-out stays disabled across page reload despite granted OS permission", async () => {
  const p = page({ optedOut: true });
  await vm.runInContext("setupPushNotifications()", p.context);
  p.listeners.get("online")();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(p.counts().saved, 0);
  assert.equal(p.counts().created, 0);
});

test("offline startup keeps the click handler and the existing subscription", async () => {
  const p = page({ offline: true });
  await vm.runInContext("setupPushNotifications()", p.context);
  assert.equal(typeof p.listeners.get("button:click"), "function");
  assert.equal(p.counts().removed, 0);
  assert.equal(p.counts().created, 0);
});

test("expired subscriptions are renewed with their previous identity", async () => {
  const p = page({ expired: true });
  await vm.runInContext("setupPushNotifications()", p.context);
  assert.equal(p.counts().removed, 1);
  assert.equal(p.counts().created, 1);
  assert.equal(p.button.dataset.state, "active");
});

test("notifications can be explicitly enabled again after opt-out", async () => {
  const p = page({ optedOut: true });
  await vm.runInContext("setupPushNotifications()", p.context);
  await p.listeners.get("button:click")();
  assert.equal(p.counts().created, 1);
  assert.equal(p.button.dataset.state, "active");
});
