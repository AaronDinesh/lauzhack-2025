# Getting Started with MX Repair Desktop

Welcome! This guide will help you get the MX Repair Desktop app up and running in minutes.

## 🚀 Quick Start (3 steps)

### 1. Install Dependencies

```bash
cd ui
npm install
```

Or use the setup script:
```bash
./scripts/setup.sh
```

### 2. Start the App

```bash
npm run electron:dev
```

Or use the dev script:
```bash
./scripts/dev.sh
```

The Electron desktop app will open automatically! 🎉

### 3. Grant Camera Access

When the app opens:
1. Click **"Grant Camera Access"**
2. Allow camera permissions
3. Select your camera from the dropdown
4. Click **"Start Camera"**

You should now see your camera feed! 📷

## 🧪 Testing with Mock Server

To test the MX Bridge integration without the full backend:

```bash
# In a new terminal
python test-server.py
```

The test server will automatically send demo events:
- Opens Wikipedia in the panel
- Toggles panel visibility
- Changes layout configuration
- Opens GitHub

Watch the UI respond to these events in real-time!

## 🎮 Using Mock Mode

Don't want to run the test server? Use built-in Mock Mode:

1. Click **Settings** (⚙️) in the top bar
2. Check **"Enable Mock Mode"**
3. Click **Save**
4. Click **"Test setUrl"** to simulate loading a URL

## 📱 What You Should See

```
┌─────────────────────────────────────────────┐
│ 🔧 MX Repair Desktop  ● Bridge  ⚙️ Settings │
├──────────────────────┬──────────────────────┤
│                      │                      │
│   Camera Feed        │    Web Panel         │
│   (your video)       │   (loaded webpage)   │
│                      │                      │
│   [Device: Webcam]   │   [example.com]      │
│   [Start] [Stop]     │   [Close]            │
│                      │                      │
└──────────────────────┴──────────────────────┘
```

## 🎯 Key Features to Try

### Camera Controls
- **Device Selection**: Switch between multiple cameras
- **Refresh**: Detect newly connected cameras
- **Start/Stop**: Control the video feed

### Web Panel
- **Auto-open**: Panel opens when receiving a URL via MX Bridge
- **External Links**: Some sites can't embed; use "Open externally"
- **YouTube**: URLs automatically convert to embeds

### Settings
- **Bridge Endpoint**: Change the SSE server URL
- **Mock Mode**: Test without a backend
- **Layout**: Panel docks left or right (via MX actions)

## 🔧 Troubleshooting

### Camera not showing?
- Click "Refresh" after connecting a camera
- Check system camera permissions
- Try restarting the app

### Can't connect to bridge?
- Make sure FastAPI server is running on port 8000
- Check the endpoint in Settings
- Enable Mock Mode for testing without a server

### Webpage won't load in panel?
- Some sites block iframe embedding (security)
- Click "Open externally" to view in browser
- YouTube URLs work automatically

### Port 3000 already in use?
- Stop other Node.js apps
- Or change the port in the Next.js dev server

## 📖 Next Steps

### Development
1. **Edit UI**: Modify components in `src/components/`
2. **Add Features**: See `ARCHITECTURE.md` for extension points
3. **Style Changes**: Update `src/app/globals.css` or Tailwind config

### Integration
1. **Connect to Backend**: Update `main.py` to send SSE events
2. **Add Actions**: Define new MX action types
3. **Camera Overlay**: Add AR features to camera view

### Production
```bash
# Build for distribution
npm run export
npm run electron:build
```

Installers will be created in the `dist/` directory.

## 📚 Documentation

- **README.md**: Full feature documentation
- **ARCHITECTURE.md**: Technical deep-dive
- **SETUP.md**: Detailed setup instructions
- **project-description.md**: Original requirements

## 🆘 Need Help?

Common commands:
```bash
# Install dependencies
npm install

# Development mode
npm run electron:dev

# Build static export
npm run export

# Package app
npm run electron:build

# Run test server
python test-server.py
```

## 🎨 Customization Ideas

- Change colors in `tailwind.config.js`
- Add custom buttons to `ControlBar.tsx`
- Implement AR overlays in `CameraView.tsx`
- Add more MX actions in `useMXBridge.ts`
- Style the app in `globals.css`

## ✨ What's Next?

The app is ready to use! Here are some ideas:

1. **Integrate with your FastAPI backend** (`main.py`)
2. **Add AR annotations** over the camera feed
3. **Implement voice commands** (already supported in backend)
4. **Add screenshot/recording** capabilities
5. **Create custom repair workflows** with step-by-step guides

Enjoy building your repair assistant! 🔧✨

---

**Pro Tip**: Keep both the desktop app and test server running during development. The app will auto-reload when you save code changes!

