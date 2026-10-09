const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("monolithDesktop", {
  notifications: {
    isSupported: () => ipcRenderer.invoke(
      "monolith:notifications-supported"
    ),
    show: payload => ipcRenderer.invoke(
      "monolith:show-notification",
      payload
    )
  }
});
