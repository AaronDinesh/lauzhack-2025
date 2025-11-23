# MX Repair Desktop

A cross-platform desktop application for hardware repair assistance with live camera feed and integrated web panel.

## Features

- 🎥 **Live Camera Feed**: Real-time video from connected cameras with device selection
- 🌐 **Web Panel**: Display web content, documentation, or guides alongside camera feed
- 🔌 **MX Bridge Integration**: Connects to FastAPI backend via Server-Sent Events (SSE)
- ⚡ **No Keyboard/Mouse Required**: Fully controlled via on-screen buttons and MX actions
- 🎨 **Modern UI**: Sleek, minimal design optimized for hardware repair workflows
- 🖥️ **Cross-Platform**: Works on Windows, macOS, and Linux

## Architecture

Built with:
- **Next.js 14** - React framework for the UI
- **Electron** - Desktop application wrapper
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Modern styling

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- A webcam/camera device
- (Optional) FastAPI backend running on `http://127.0.0.1:8000/stream`

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Run Next.js development server
npm run dev

# Run Electron in development mode (in separate terminal)
npm run electron:dev
```

The app will open in an Electron window and hot-reload as you make changes.

### Production Build

```bash
# Build Next.js static export
npm run export

# Package Electron app
npm run electron:build
```

## Configuration

### Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_MX_BRIDGE_URL=http://127.0.0.1:8000/stream
```

You can also configure the bridge endpoint through the Settings UI.

### Camera Setup

1. Click "Grant Camera Access" to request camera permissions
2. Select your camera from the dropdown
3. Click "Start Camera" to begin the video feed
4. Use "Refresh" if you connect a new camera device

## MX Bridge Protocol

The app connects to a FastAPI backend via SSE and listens for JSON action messages:

### Supported Actions

#### `setUrl`
Open a URL in the web panel:
```json
{"type": "setUrl", "payload": {"url": "https://example.com"}}
```

#### `togglePanel`
Show/hide the web panel:
```json
{"type": "togglePanel"}
```

#### `triggerStep`
Trigger a workflow step:
```json
{"type": "triggerStep", "payload": {"step": "step-name"}}
```

#### `setLayout`
Configure panel layout:
```json
{
  "type": "setLayout",
  "payload": {
    "dockSide": "left",
    "workspaceSplit": 60
  }
}
```

#### `setMockMode`
Enable/disable mock mode for testing:
```json
{"type": "setMockMode", "payload": {"enabled": true}}
```

#### `setBridgeEndpoint`
Change the SSE endpoint:
```json
{"type": "setBridgeEndpoint", "payload": {"endpoint": "http://localhost:9000/stream"}}
```

## Project Structure

```
ui/
├── electron/           # Electron main process
│   └── main.js
├── src/
│   ├── app/           # Next.js app directory
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/    # React components
│   │   ├── CameraView.tsx
│   │   ├── WebPanel.tsx
│   │   └── ControlBar.tsx
│   └── hooks/         # Custom React hooks
│       └── useMXBridge.ts
├── package.json
├── next.config.js
├── tsconfig.json
└── tailwind.config.js
```

## Usage Tips

### Mock Mode

Enable Mock Mode in Settings to test the UI without a backend:
1. Click Settings (⚙️)
2. Check "Enable Mock Mode"
3. Click "Test setUrl" to simulate loading a URL

### Camera Troubleshooting

- If camera doesn't appear, click "Refresh" after connecting
- Check browser/Electron permissions if access is denied
- Some USB cameras may need to be unplugged/replugged

### Web Panel

- Most sites can be loaded via iframe
- If a site blocks embedding, use "Open externally"
- YouTube URLs are automatically converted to embed format

## Development Notes

- The app uses Next.js static export (`output: 'export'`) for Electron
- Camera access requires HTTPS or localhost (Electron provides this)
- SSE connection auto-reconnects every 5 seconds on failure

## License

MIT

