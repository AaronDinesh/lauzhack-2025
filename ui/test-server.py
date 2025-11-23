#!/usr/bin/env python3
"""
Simple FastAPI test server for MX Repair Desktop.
Sends mock SSE events to test the UI.

Usage:
    python test-server.py
"""

import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MX Bridge Test Server")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def event_generator():
    """Generate mock SSE events for testing."""
    
    # Wait a bit before sending first event
    await asyncio.sleep(2)
    
    # Example: Set a URL after 2 seconds
    yield f"data: {json.dumps({'type': 'setUrl', 'payload': {'url': 'https://www.wikipedia.org'}})}\n\n"
    
    await asyncio.sleep(5)
    
    # Example: Toggle panel
    yield f"data: {json.dumps({'type': 'togglePanel'})}\n\n"
    
    await asyncio.sleep(3)
    
    # Example: Toggle panel back
    yield f"data: {json.dumps({'type': 'togglePanel'})}\n\n"
    
    await asyncio.sleep(3)
    
    # Example: Load another URL
    yield f"data: {json.dumps({'type': 'setUrl', 'payload': {'url': 'https://github.com'}})}\n\n"
    
    await asyncio.sleep(5)
    
    # Example: Change layout
    yield f"data: {json.dumps({'type': 'setLayout', 'payload': {'dockSide': 'left', 'workspaceSplit': 50}})}\n\n"
    
    await asyncio.sleep(5)
    
    # Example: Change layout back
    yield f"data: {json.dumps({'type': 'setLayout', 'payload': {'dockSide': 'right', 'workspaceSplit': 70}})}\n\n"
    
    # Keep connection alive with periodic heartbeats
    while True:
        await asyncio.sleep(30)
        yield ": heartbeat\n\n"


@app.get("/stream")
async def stream():
    """SSE endpoint that streams MX actions."""
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "MX Bridge Test Server",
        "version": "1.0.0",
        "endpoints": {
            "stream": "/stream (SSE)",
        },
        "actions": [
            "setUrl",
            "togglePanel",
            "triggerStep",
            "setLayout",
            "setMockMode",
            "setBridgeEndpoint",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("MX Bridge Test Server")
    print("=" * 60)
    print("Server starting at: http://127.0.0.1:8000")
    print("SSE endpoint: http://127.0.0.1:8000/stream")
    print("\nThis server will send mock events to test the UI.")
    print("Connect your MX Repair Desktop app to see them in action!")
    print("=" * 60)
    
    uvicorn.run(app, host="127.0.0.1", port=8000)

