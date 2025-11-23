# MX Repair Desktop – Current State (Nov 2025)

## High-Level Overview
MX Repair Desktop is now a two-part system for hardware repair assistance:

- A **Python multimodal voice loop** (`main.py`, `audio/`, `camera/`) lets a technician hold SPACE to talk, captures a synchronized webcam frame, sends both to OpenAI’s Responses API, and plays the reply through low-latency text-to-speech.
- A **Next.js 14 + Electron desktop shell** (`ui/`) keeps a live camera preview on screen and exposes an MX-controlled web panel that can be driven over Server-Sent Events (SSE) from a FastAPI bridge.

Both halves share the same goal: hands-free, glanceable guidance with minimal UI chrome.

## Repository At A Glance
- `main.py`: end-to-end press-to-speak loop (audio capture → STT → camera screenshot → OpenAI response → TTS playback).
- `audio/`: space-bar recorder (`record_press_to_speak`), OpenAI transcription helpers, and streaming / buffered speech synthesis.
- `camera/`: frame cache, single-frame capture utilities, preview + prompt CLIs, plus JPEG logging under `logs/`.
- `ui/`: production-ready desktop shell (Next.js app, Electron wrapper, scripts, docs, static export, FastAPI mock server).

## Current Capabilities
- **Voice-first workflow**: `pynput` listens for the space bar, `sounddevice` streams PCM into a temp WAV, and `audio/speech_to_text.py` ships it to `gpt-4o-mini-transcribe`.
- **Vision context**: `camera/helpers.py` maintains a background `FrameCache`, persists every screenshot, and builds OpenAI-ready image payloads alongside the spoken prompt.
- **OpenAI Responses loop**: `main.py` streams partial assistant text, logs per-step latency, maintains full conversation history, and retries gracefully if the API fails.
- **Speech playback**: `audio/text_to_speech.py` streams PCM straight into `sounddevice.RawOutputStream` for minimal delay, with fallbacks for WAV/AIFF formats.
- **Desktop UI**: Electron launches the exported Next.js app, showing a full-bleed camera workspace with a dockable web panel, control bar, and status indicators tailored for touch / pointer-free use.

## MX Bridge / SSE Actions (UI)
- Default SSE endpoint: `http://127.0.0.1:8000/stream`, configurable via Settings or `NEXT_PUBLIC_MX_BRIDGE_URL`.
- `useMXBridge` hook keeps a persistent EventSource connection with automatic 5 s reconnects and exposes connection/error state to the control bar.
- Supported action types: `setUrl`, `togglePanel`, `triggerStep`, `setLayout` (`dockSide`, `workspaceSplit`), `setMockMode`, `setBridgeEndpoint`.
- Mock mode exposes a “Test setUrl” button so designers can demo panel swaps without the backend.
- `ui/test-server.py` (FastAPI) can stream scripted MX actions plus keep-alive heartbeats for local testing.

## Camera Experience (UI)
- “Grant Camera Access” prompts `getUserMedia` permission, then enumerates `videoinput` devices.
- Device dropdown, manual refresh, and explicit Start/Stop controls manage the `MediaStream`.
- Streams are stopped on device changes or when the component unmounts to free hardware resources.
- Idle state presents guidance copy so the operator always knows what to do next.

## Web Panel Behavior
- Single iframe that normalizes URLs (auto-https, YouTube watch/embed swap) and keys the iframe by URL for forced reloads.
- Sandbox: `allow-same-origin allow-scripts allow-popups allow-forms`.
- When a site blocks embedding, the panel shows a friendly fallback and offers “Open externally”.
- Width is derived from `workspaceSplit`; panel can dock left or right while preserving camera focus.

## How The Pieces Fit Today
1. **Hands-free conversation**: Run `python main.py` at the repo root. Hold SPACE to speak, release to submit. The pipeline captures audio + a photo, sends both to OpenAI, and speaks the answer aloud. Every turn logs a screenshot under `logs/`.
2. **Visual workstation**: Run `npm run electron:dev` inside `ui/` (or use `./scripts/dev.sh`). Connect it to the FastAPI SSE endpoint (either your own server or `python test-server.py`) to let MX actions open documentation, toggle the panel, or adjust the layout.
3. **Event bridge**: The architecture diagram in `ui/ARCHITECTURE.md` shows how a backend such as `main.py` can emit SSE actions so the desktop shell mirrors what the assistant is doing (load guides, highlight steps, switch overlays).

## Open Threads / Next Steps
- Wire `main.py` (or another FastAPI service) to actually emit the MX actions currently being consumed via the mock server, so the voice agent and Electron shell stay in sync.
- Layer optional AR/segmentation overlays by extending `camera/helpers.FrameCache` outputs or React’s `CameraView`.
- Add workflow-specific `triggerStep` handling once the MX automation contract is finalized.

The project is usable end-to-end today: the Python loop delivers real multimodal conversations with OpenAI, and the Electron app offers a polished control surface for technicians, ready to be tethered to live MX actions.
