# Setup Instructions

Follow these steps to set up and run the MX Repair Desktop application.

## Quick Start

### 1. Install Dependencies

```bash
cd ui
npm install
```

This will install all required Node.js packages including Next.js, React, Electron, and Tailwind CSS.

### 2. Run Development Mode

**Option A: Next.js Only (Browser)**
```bash
npm run dev
```
Then open http://localhost:3000 in your browser.

**Option B: Electron App (Recommended)**
```bash
npm run electron:dev
```
This will start both Next.js and Electron. The desktop app will open automatically.

### 3. (Optional) Start Test Server

To test the MX Bridge SSE integration, run the included test server:

```bash
python test-server.py
```

The test server will send mock events to demonstrate:
- Opening URLs in the panel
- Toggling panel visibility
- Changing layout configuration

## Configuration

### Camera Permissions

On first run:
1. Click "Grant Camera Access"
2. Allow camera permissions when prompted
3. Select your camera from the dropdown
4. Click "Start Camera"

### MX Bridge Connection

The app will attempt to connect to `http://127.0.0.1:8000/stream` by default.

To change the endpoint:
1. Click Settings (⚙️) in the top bar
2. Enter your FastAPI SSE endpoint
3. Click Save

Alternatively, create a `.env.local` file:
```env
NEXT_PUBLIC_MX_BRIDGE_URL=http://your-server:port/stream
```

## Building for Production

### Export Static Files

```bash
npm run export
```

This creates an optimized static build in the `out/` directory.

### Package Electron App

```bash
npm run electron:build
```

This will create distributable packages for your current platform in the `dist/` directory.

## Testing Without Backend

Enable Mock Mode for testing without a running backend:

1. Open Settings (⚙️)
2. Check "Enable Mock Mode"
3. Click "Test setUrl" to simulate receiving a URL command

## Troubleshooting

### Port Already in Use

If port 3000 is already in use, Next.js will prompt you to use a different port. Update the Electron main process accordingly or stop the conflicting service.

### Camera Not Detected

- Try clicking "Refresh" after connecting a camera
- Check system camera permissions
- Restart the app if camera was connected after launch
- On macOS: System Preferences → Security & Privacy → Camera

### SSE Connection Failed

- Ensure your FastAPI server is running
- Check that the endpoint URL is correct in Settings
- Verify CORS is enabled on your backend
- Check the console for detailed error messages

### Iframe Blocked

Some websites prevent iframe embedding. If you see "Unable to load in iframe":
- Click "Open externally" to view in a regular browser
- This is a security feature of those websites, not a bug

## Development Tips

### Hot Reload

In development mode, the UI will hot-reload when you save changes to:
- React components (`src/components/`)
- Pages (`src/app/`)
- Stylesheets (`src/app/globals.css`)

The Electron window will need to be reloaded manually (Cmd/Ctrl+R) when you change:
- Electron main process (`electron/main.js`)
- Next.js configuration (`next.config.js`)

### Inspecting the App

In Electron development mode, DevTools are automatically opened. You can also:
- Toggle DevTools: Cmd+Option+I (Mac) or Ctrl+Shift+I (Windows/Linux)
- Reload: Cmd+R (Mac) or Ctrl+R (Windows/Linux)

### Testing SSE Events

Use the included `test-server.py` or send events manually with curl:

```bash
# Keep connection open and send events
curl -N http://localhost:8000/stream
```

Or send custom events from your own FastAPI endpoint:

```python
async def event_generator():
    yield f"data: {json.dumps({'type': 'setUrl', 'payload': {'url': 'https://example.com'}})}\n\n"
```

## Next Steps

1. Integrate with your existing FastAPI backend (`main.py`)
2. Customize the camera overlay or add AR features
3. Add additional MX actions as needed
4. Style the UI to match your brand
5. Add logging and analytics

Enjoy building with MX Repair Desktop! 🔧

