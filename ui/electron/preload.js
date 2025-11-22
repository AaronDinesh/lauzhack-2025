const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  togglePanel: (url) => ipcRenderer.invoke('panel:toggle', url),
  loadPanel: (url) => ipcRenderer.invoke('panel:load', url),
  resizePanel: (fraction, topOffset) =>
    ipcRenderer.invoke('panel:resize', { fraction, topOffset }),
});
