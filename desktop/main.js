const {
  app,
  BrowserWindow,
  ipcMain,
  Notification,
  screen,
  shell
} = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const dashboardUrl = process.env.MONOLITH_URL || "https://monolith.local";
const dashboardOrigin = new URL(dashboardUrl).origin;
const offlinePage = path.join(__dirname, "offline.html");
const offlinePageUrl = pathToFileURL(offlinePage).href;
const defaultZoomFactor = 1.15;
const zoomStep = 0.1;
const minimumZoomFactor = 0.75;
const maximumZoomFactor = 2;
const activeNotifications = new Set();
const appUserModelId = "local.monolith.desktop";

app.setAppUserModelId(appUserModelId);

function isDashboardUrl(rawUrl) {
  try {
    return new URL(rawUrl).origin === dashboardOrigin;
  } catch {
    return false;
  }
}

function openExternal(rawUrl) {
  if (rawUrl.startsWith("https://") || rawUrl.startsWith("http://")) {
    void shell.openExternal(rawUrl);
  }
}

function isDashboardSender(event) {
  return isDashboardUrl(event.senderFrame?.url || "");
}

function cleanNotificationText(value, fallback, maximumLength) {
  const text = typeof value === "string"
    ? value.trim()
    : "";

  return (text || fallback).slice(0, maximumLength);
}

function getNotificationTarget(rawUrl) {
  try {
    const target = new URL(
      typeof rawUrl === "string" ? rawUrl : "/",
      dashboardOrigin
    );

    return target.origin === dashboardOrigin
      ? target.href
      : dashboardUrl;
  } catch {
    return dashboardUrl;
  }
}

function ensureWindowsShortcut() {
  if (process.platform !== "win32" || !app.isPackaged) {
    return;
  }

  const shortcutPath = path.join(
    app.getPath("appData"),
    "Microsoft",
    "Windows",
    "Start Menu",
    "Programs",
    "MONOLITH.lnk"
  );
  const shortcutUpdated = shell.writeShortcutLink(
    shortcutPath,
    "replace",
    {
      target: process.execPath,
      cwd: path.dirname(process.execPath),
      description: "MONOLITH Dashboard",
      icon: process.execPath,
      iconIndex: 0,
      appUserModelId
    }
  );

  if (!shortcutUpdated) {
    console.warn("MONOLITH-Startmenüverknüpfung konnte nicht aktualisiert werden");
  }
}

function getWindowStatePath() {
  return path.join(app.getPath("userData"), "window-state.json");
}

function getSavedWindowState() {
  try {
    const state = JSON.parse(fs.readFileSync(getWindowStatePath(), "utf8"));
    const bounds = state?.bounds;
    const hasValidBounds = bounds
      && [bounds.x, bounds.y, bounds.width, bounds.height]
        .every(Number.isFinite)
      && bounds.width >= 800
      && bounds.height >= 600;

    if (!hasValidBounds) {
      return null;
    }

    const isVisible = screen.getAllDisplays().some(({ workArea }) => {
      const visibleWidth = Math.min(
        bounds.x + bounds.width,
        workArea.x + workArea.width
      ) - Math.max(bounds.x, workArea.x);
      const visibleHeight = Math.min(
        bounds.y + bounds.height,
        workArea.y + workArea.height
      ) - Math.max(bounds.y, workArea.y);

      return visibleWidth >= 100 && visibleHeight >= 100;
    });

    return isVisible
      ? { bounds, isMaximized: state.isMaximized === true }
      : null;
  } catch (error) {
    if (error.code !== "ENOENT") {
      console.warn("Fensterzustand konnte nicht gelesen werden:", error);
    }
    return null;
  }
}

function saveWindowState(window) {
  try {
    const state = {
      bounds: window.getNormalBounds(),
      isMaximized: window.isMaximized()
    };
    fs.writeFileSync(getWindowStatePath(), JSON.stringify(state), "utf8");
  } catch (error) {
    console.warn("Fensterzustand konnte nicht gespeichert werden:", error);
  }
}

ipcMain.handle("monolith:notifications-supported", event => {
  return isDashboardSender(event) && Notification.isSupported();
});

ipcMain.handle("monolith:show-notification", async (event, payload = {}) => {
  if (!isDashboardSender(event) || !Notification.isSupported()) {
    return false;
  }

  const sourceWindow = BrowserWindow.fromWebContents(event.sender);
  const targetUrl = getNotificationTarget(payload.url);
  const notification = new Notification({
    title: cleanNotificationText(payload.title, "MONOLITH", 80),
    body: cleanNotificationText(payload.body, "Neue Mitteilung", 240),
    icon: path.join(__dirname, "assets", "icon.png")
  });

  activeNotifications.add(notification);
  notification.once("close", () => {
    activeNotifications.delete(notification);
  });

  notification.on("click", () => {
    if (!sourceWindow || sourceWindow.isDestroyed()) {
      return;
    }

    if (sourceWindow.isMinimized()) {
      sourceWindow.restore();
    }
    sourceWindow.show();
    sourceWindow.focus();
    void sourceWindow.loadURL(targetUrl);
  });
  return await new Promise(resolve => {
    let finished = false;

    const finish = result => {
      if (finished) {
        return;
      }
      finished = true;
      resolve(result);
    };

    notification.once("show", () => finish(true));
    notification.once("failed", (_event, error) => {
      console.error("Desktop-Benachrichtigung fehlgeschlagen:", error);
      activeNotifications.delete(notification);
      finish(false);
    });
    notification.show();
    setTimeout(() => finish(false), 3000);
  });
});

function createWindow() {
  let currentZoomFactor = defaultZoomFactor;
  const savedWindowState = getSavedWindowState();
  const window = new BrowserWindow({
    width: savedWindowState?.bounds.width ?? 1280,
    height: savedWindowState?.bounds.height ?? 820,
    x: savedWindowState?.bounds.x,
    y: savedWindowState?.bounds.y,
    minWidth: 800,
    minHeight: 600,
    show: false,
    backgroundColor: "#090b10",
    autoHideMenuBar: true,
    icon: path.join(__dirname, "assets", "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, "preload.js"),
      zoomFactor: defaultZoomFactor
    }
  });

  window.once("ready-to-show", () => {
    if (savedWindowState?.isMaximized) {
      window.maximize();
    }
    window.show();
  });

  window.on("close", () => {
    saveWindowState(window);
  });

  function setZoomFactor(zoomFactor) {
    currentZoomFactor = Math.min(
      maximumZoomFactor,
      Math.max(minimumZoomFactor, Math.round(zoomFactor * 100) / 100)
    );
    window.webContents.setZoomFactor(currentZoomFactor);
  }

  window.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown" || (!input.control && !input.meta)) {
      return;
    }

    const zoomIn = input.key === "+" || input.key === "=" || input.code === "NumpadAdd";
    const zoomOut = input.key === "-" || input.code === "NumpadSubtract";
    const resetZoom = input.key === "0" || input.code === "Numpad0";

    if (zoomIn) {
      event.preventDefault();
      setZoomFactor(currentZoomFactor + zoomStep);
    } else if (zoomOut) {
      event.preventDefault();
      setZoomFactor(currentZoomFactor - zoomStep);
    } else if (resetZoom) {
      event.preventDefault();
      setZoomFactor(defaultZoomFactor);
    }
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isDashboardUrl(url)) {
      void window.loadURL(url);
    } else {
      openExternal(url);
    }

    return { action: "deny" };
  });

  window.webContents.on("will-navigate", (event, url) => {
    if (isDashboardUrl(url) || url.startsWith(offlinePageUrl)) {
      return;
    }

    event.preventDefault();
    openExternal(url);
  });

  window.webContents.on(
    "did-fail-load",
    (_event, errorCode, _errorDescription, validatedUrl, isMainFrame) => {
      if (!isMainFrame || errorCode === -3 || !isDashboardUrl(validatedUrl)) {
        return;
      }

      void window.loadFile(offlinePage, {
        query: { target: dashboardUrl }
      });
    }
  );

  void window.loadURL(dashboardUrl);
}

app.whenReady().then(() => {
  ensureWindowsShortcut();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
