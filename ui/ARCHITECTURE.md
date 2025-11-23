# Architecture Overview

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    MX Repair Desktop                         │
│                    (Electron + Next.js)                      │
│                                                              │
│  ┌────────────────┐                  ┌──────────────────┐   │
│  │                │                  │                  │   │
│  │  Camera View   │                  │   Web Panel      │   │
│  │                │                  │                  │   │
│  │  - Device sel  │                  │  - URL loading   │   │
│  │  - Start/Stop  │                  │  - Iframe        │   │
│  │  - Live feed   │                  │  - External open │   │
│  │                │                  │                  │   │
│  └────────────────┘                  └──────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Control Bar & Settings                  │   │
│  │  - Bridge status  - Mock mode  - Settings           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              MX Bridge Hook (SSE)                    │   │
│  │  - Connect to FastAPI                                │   │
│  │  - Handle MX actions                                 │   │
│  │  - Auto-reconnect                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↕
                    Server-Sent Events (SSE)
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│                    (main.py)                                 │
│                                                              │
│  - Audio recording & transcription                          │
│  - Camera capture & vision processing                       │
│  - OpenAI multimodal chat                                   │
│  - Text-to-speech                                           │
│  - SSE endpoint for UI control                              │
└─────────────────────────────────────────────────────────────┘
```

## Component Hierarchy

```
App (page.tsx)
├── ControlBar
│   └── Settings Modal
├── CameraView
│   ├── Device Selector
│   ├── Control Buttons
│   └── Video Element
└── WebPanel
    ├── Panel Header
    └── Iframe / Error State
```

## Data Flow

### 1. MX Bridge Connection (SSE)

```typescript
FastAPI /stream
    ↓
EventSource connection
    ↓
useMXBridge hook
    ↓
Callbacks in page.tsx
    ↓
State updates (panelUrl, panelVisible, etc.)
    ↓
Re-render components
```

### 2. Camera Lifecycle

```typescript
User clicks "Start Camera"
    ↓
Request getUserMedia()
    ↓
Store MediaStream in ref
    ↓
Assign to video.srcObject
    ↓
Video plays automatically
```

### 3. Panel URL Loading

```typescript
SSE: setUrl action received
    ↓
Normalize URL (add https, YouTube rewrite)
    ↓
Update iframe src with key={url}
    ↓
Force reload via React key
    ↓
Handle iframe errors gracefully
```

## Key Technologies

### Frontend
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type safety throughout
- **Tailwind CSS**: Utility-first styling
- **React Hooks**: State management

### Desktop
- **Electron 28**: Cross-platform desktop wrapper
- **electron-builder**: Build and packaging

### Communication
- **EventSource API**: Server-Sent Events (SSE)
- **MediaDevices API**: Camera access
- **Iframe**: Web content embedding

## State Management

The app uses React's built-in state management with hooks:

### Global State (page.tsx)
- `panelVisible`: Boolean - panel open/closed
- `panelUrl`: String - current URL to load
- `bridgeEndpoint`: String - SSE endpoint URL
- `mockMode`: Boolean - testing mode
- `dockSide`: 'left' | 'right' - panel position
- `workspaceSplit`: Number - percentage split

### Local State (Components)
Each component manages its own internal state:
- CameraView: devices, selectedDevice, cameraActive, error
- WebPanel: normalizedUrl, iframeError
- ControlBar: showSettings, endpointInput

## MX Actions Protocol

All actions follow this JSON structure:

```typescript
{
  type: 'actionName',
  payload?: {
    // Action-specific data
  }
}
```

### Action Types

| Action | Purpose | Payload |
|--------|---------|---------|
| `setUrl` | Load URL in panel | `{url: string}` |
| `togglePanel` | Show/hide panel | None |
| `triggerStep` | Trigger workflow | `{step: string}` |
| `setLayout` | Change layout | `{dockSide?, workspaceSplit?}` |
| `setMockMode` | Toggle mock mode | `{enabled: boolean}` |
| `setBridgeEndpoint` | Change SSE URL | `{endpoint: string}` |

## Security Considerations

### Iframe Sandboxing
Iframes use restricted sandbox permissions:
```html
sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
```

### Camera Permissions
- getUserMedia() requires user consent
- Only works on HTTPS or localhost
- Electron provides secure context automatically

### Content Security
- No `nodeIntegration` in Electron
- Context isolation enabled
- Web security enforced

## Performance Optimizations

1. **Camera Stream**: Stored in ref to prevent re-renders
2. **Iframe Key**: Forces reload only when URL changes
3. **SSE Reconnect**: 5-second delay prevents spam
4. **Video Constraints**: Request ideal resolution, fall back gracefully
5. **Static Export**: Pre-rendered HTML for fast load

## Error Handling

### Camera Errors
- Permission denied → Show grant access button
- Device not found → Show device list as empty
- Stream failed → Display error message

### SSE Errors
- Connection failed → Show disconnected status
- Auto-reconnect after 5 seconds
- Parse errors → Log to console, continue

### Iframe Errors
- Load failed → Show "Open externally" option
- X-Frame-Options blocked → Graceful fallback
- Invalid URL → Validation before loading

## Build Process

### Development
```bash
npm run dev           # Next.js dev server (port 3000)
npm run electron:dev  # Next.js + Electron
```

### Production
```bash
npm run export        # Static export to out/
npm run electron:build # Package with electron-builder
```

Build outputs:
- `out/`: Static HTML/JS/CSS
- `dist/`: Platform-specific installers

## Extension Points

### Adding New MX Actions

1. Update `MXAction` type in `useMXBridge.ts`
2. Add handler in the switch statement
3. Add callback interface
4. Implement in `page.tsx`

### Adding Camera Overlays

1. Add overlay elements in `CameraView.tsx`
2. Position absolutely over video element
3. Use canvas for annotations/segmentation
4. Sync with camera state

### Custom Styling

1. Update `tailwind.config.js` for theme colors
2. Modify `globals.css` for custom classes
3. Component styles in respective `.tsx` files

## Future Enhancements

Potential improvements:
- [ ] Multiple camera views (picture-in-picture)
- [ ] AR overlays with object detection
- [ ] Recording/screenshot capabilities
- [ ] Panel split view (multiple URLs)
- [ ] Keyboard shortcuts
- [ ] Gesture controls via camera
- [ ] Voice commands integration
- [ ] Real-time annotations
- [ ] Session history/replay
- [ ] Cloud sync for settings

## Integration with Existing Backend

The desktop app is designed to work alongside your existing `main.py`:

1. **Camera Feed**: Complements frame cache in `camera/helpers.py`
2. **Audio**: Can trigger voice input from UI buttons
3. **Vision**: Can send screenshots to OpenAI pipeline
4. **SSE**: New endpoint to add to FastAPI server

Example FastAPI integration:

```python
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

@app.get("/stream")
async def stream_events():
    async def event_generator():
        # Your logic here
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "setUrl",
                "payload": {"url": "https://docs.example.com"}
            })
        }
    
    return EventSourceResponse(event_generator())
```

This architecture provides a solid foundation for a professional hardware repair assistance tool! 🔧

