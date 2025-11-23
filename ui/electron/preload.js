const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  togglePanel: (url) => ipcRenderer.invoke('panel:toggle', url),
  loadPanel: (url) => ipcRenderer.invoke('panel:load', url),
  resizePanel: (fraction, topOffset) =>
    ipcRenderer.invoke('panel:resize', { fraction, topOffset }),
  detachPanel: () => ipcRenderer.invoke('panel:detach'),
  attachPanel: () => ipcRenderer.invoke('panel:attach'),
  capturePanel: () => ipcRenderer.invoke('panel:capture'),
  sendFrame: (bytes) => ipcRenderer.invoke('frame:send', bytes),
  setFrameEndpoint: (endpoint) => ipcRenderer.invoke('frame:setEndpoint', endpoint),
});
