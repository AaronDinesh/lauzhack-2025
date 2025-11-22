const { app, BrowserWindow, BrowserView, ipcMain } = require('electron');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';
const panelUrl = process.env.PANEL_URL || 'https://example.com';

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

  let panelVisible = false;

  const updatePanelBounds = () => {
    const [width, height] = mainWindow.getContentSize();
    // Dock the panel on the right; leave room for the main content.
    panelView.setBounds({
      x: Math.floor(width * 0.6),
      y: 0,
      width: Math.floor(width * 0.4),
      height,
    });
  };

  const showPanel = async (urlToLoad) => {
    const url = urlToLoad || panelUrl;
    await panelView.webContents.loadURL(url);
    mainWindow.setBrowserView(panelView);
    updatePanelBounds();
    panelVisible = true;
  };

  const hidePanel = () => {
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
    if (panelVisible) {
      await panelView.webContents.loadURL(requestedUrl || panelUrl);
      return true;
    }
    await showPanel(requestedUrl);
    return true;
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
    hidePanel();
    ipcMain.removeHandler('panel:toggle');
    ipcMain.removeHandler('panel:load');
    app.quit();
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
