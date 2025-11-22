const { app, BrowserWindow, BrowserView, ipcMain } = require('electron');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';

const sanitizeUrl = (url) => {
  if (!url) return '';
  const trimmed = url.trim();
  return trimmed;
};

const defaultPanelUrl = sanitizeUrl(process.env.PANEL_URL) || 'https://example.com';
const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const PANEL_HANDLE_WIDTH = 8; // keep in sync with renderer

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    backgroundColor: '#0a0a0a',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    titleBarStyle: 'hiddenInset',
    frame: true,
  });

  const panelView = new BrowserView({
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  });
  panelView.setAutoResize({ width: true, height: true });

  let panelVisible = false;
  let lastPanelUrl = defaultPanelUrl;
  let panelSplit = 0.4; // fraction of window width reserved for panel
  let controlBarOffset = 0; // pixels to offset panel from top (height of control bar)
  let panelInitialized = false;

  const updatePanelBounds = () => {
    const [width, height] = mainWindow.getContentSize();
    // Dock the panel on the right; leave room for the main content and handle.
    const cameraFraction = 1 - panelSplit;
    const cameraWidth = Math.max(0, Math.round(width * cameraFraction));
    const panelWidth = Math.max(0, width - cameraWidth - PANEL_HANDLE_WIDTH);
    const panelX = cameraWidth + PANEL_HANDLE_WIDTH;

    const offsetY = Math.max(0, Math.floor(controlBarOffset));
    const effectiveHeight = Math.max(0, height - offsetY);
    panelView.setBounds({
      x: Math.max(0, panelX),
      y: offsetY,
      width: panelWidth,
      height: effectiveHeight,
    });
  };

  const loadPanelUrl = async (url) => {
    try {
      await panelView.webContents.loadURL(url);
      panelInitialized = true;
      return true;
    } catch (err) {
      // Swallow aborted navigations to avoid noisy errors when sites self-redirect.
      if (err?.code === 'ERR_ABORTED') {
        return true;
      }
      console.error('Failed to load panel URL:', url, err);
      return false;
    }
  };

  const showPanel = async (urlToLoad, forceReload = false) => {
    const sanitized = sanitizeUrl(urlToLoad);
    const fallback = sanitizeUrl(lastPanelUrl) || sanitizeUrl(defaultPanelUrl);
    const url = sanitized || fallback;
    if (!url) {
      throw new Error('No URL provided for panel');
    }

    const shouldReload = forceReload || !panelInitialized || url !== lastPanelUrl;
    if (shouldReload) {
      const ok = await loadPanelUrl(url);
      if (!ok) return false;
      lastPanelUrl = url;
    }

    mainWindow.setBrowserView(panelView);
    updatePanelBounds();
    panelVisible = true;
    return true;
  };

  const hidePanel = () => {
    const destroyed = panelView.webContents.isDestroyed();
    if (panelVisible && destroyed) {
      panelVisible = false;
      return;
    }
    if (!panelVisible) return;
    mainWindow.removeBrowserView(panelView);
    panelVisible = false;
  };

  ipcMain.handle('panel:toggle', async (_event, requestedUrl) => {
    if (panelVisible) {
      hidePanel();
      return false;
    }

    await showPanel(requestedUrl);
    return true;
  });

  ipcMain.handle('panel:load', async (_event, requestedUrl) => {
    const sanitized = sanitizeUrl(requestedUrl);
    const fallback = sanitizeUrl(lastPanelUrl) || sanitizeUrl(defaultPanelUrl);
    const url = sanitized || fallback;
    if (!url) {
      throw new Error('No URL provided for panel');
    }

    if (panelVisible) {
      const ok = await loadPanelUrl(url);
      if (ok) {
        lastPanelUrl = url;
        return true;
      }
      return false;
    }

    return showPanel(url);
  });

  ipcMain.handle('panel:resize', async (_event, payload) => {
    const { fraction, topOffset } =
      typeof payload === 'object' ? payload : { fraction: payload };

    const nextSplit = clamp(Number(fraction) || panelSplit, 0.2, 0.8);
    const nextOffset = clamp(Number(topOffset) || 0, 0, 2000);

    panelSplit = nextSplit;
    controlBarOffset = nextOffset;
    if (panelVisible) {
      updatePanelBounds();
    }
    return { panelSplit, controlBarOffset };
  });

  mainWindow.on('resize', () => {
    if (panelVisible) {
      updatePanelBounds();
    }
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../out/index.html'));
  }

  mainWindow.on('closed', () => {
    try {
      hidePanel();
    } catch (e) {
      // ignore
    }
    ipcMain.removeHandler('panel:toggle');
    ipcMain.removeHandler('panel:load');
    ipcMain.removeHandler('panel:resize');
    if (!app.isQuitting) {
      app.quit();
    }
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
