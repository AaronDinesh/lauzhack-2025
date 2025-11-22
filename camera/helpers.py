"""
Shared camera utilities for capturing frames, persisting screenshots, and
preparing OpenAI-ready content blocks.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from time import time
from typing import Any, Dict, List, Optional

import cv2  # type: ignore

LOGS_DIR = Path(__file__).resolve().parents[1] / "logs"


class FrameCache:
    """
    Background camera reader that keeps the device open and refreshes JPEG data
    at a fixed interval. Consumers can fetch the most recent frame without
    paying the capture setup cost every time.
    """

    def __init__(self, *, camera_index: int = 0, refresh_interval: float = 0.5):
        self._camera_index = camera_index
        self._refresh_interval = refresh_interval
        self._latest_frame: Optional[bytes] = None
        self._latest_ts: float = 0.0
        self._lock = Lock()
        self._stop = Event()
        self._ready = Event()
        self._thread: Optional[Thread] = None
        self._error: Optional[Exception] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._ready.clear()
        self._thread = Thread(target=self._run, name="FrameCache", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def wait_until_ready(self, timeout: float = 3.0) -> None:
        """
        Block until the first frame arrives or timeout expires. Raises any
        startup error encountered by the worker thread.
        """
        if not self._thread:
            raise RuntimeError("FrameCache has not been started")
        self._ready.wait(timeout)
        if self._error:
            raise self._error
        if not self._ready.is_set():
            raise TimeoutError("FrameCache did not deliver a frame in time")

    def get_latest_frame(self, *, max_age: Optional[float] = None) -> Optional[bytes]:
        with self._lock:
            frame = self._latest_frame
            ts = self._latest_ts
        if frame is None:
            return None
        if max_age is not None and (time() - ts) > max_age:
            return None
        return frame

    def _run(self) -> None:
        capture = cv2.VideoCapture(self._camera_index)
        if not capture.isOpened():
            self._error = RuntimeError(
                f"Unable to open camera at index {self._camera_index}"
            )
            self._ready.set()
            return

        try:
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue

                ok, buffer = cv2.imencode(".jpg", frame)
                if ok:
                    with self._lock:
                        self._latest_frame = buffer.tobytes()
                        self._latest_ts = time()
                    self._ready.set()

                if self._stop.wait(self._refresh_interval):
                    break
        finally:
            capture.release()


def capture_frame(camera_index: int = 0) -> bytes:
    """Capture one JPEG-encoded frame from the specified camera index."""
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open camera at index {camera_index}")

    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError("Failed to capture a frame from the camera")

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Failed to encode frame as JPEG")

        return buffer.tobytes()
    finally:
        capture.release()


def jpeg_bytes_to_data_url(jpeg_bytes: bytes) -> str:
    """Convert JPEG bytes to a base64 data URL."""
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def save_frame_to_logs(jpeg_bytes: bytes, logs_dir: Path = LOGS_DIR) -> Path:
    """Persist the captured frame into the logs directory."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = logs_dir / f"screenshot-{timestamp}.jpg"
    destination.write_bytes(jpeg_bytes)
    return destination


def build_image_content(message: str, jpeg_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Build an OpenAI content list containing the user's text plus the image of the
    latest camera frame.
    """
    image_url = jpeg_bytes_to_data_url(jpeg_bytes)
    return [
        {"type": "input_text", "text": message},
        {"type": "input_image", "image_url": image_url},
    ]


def capture_with_context(
    message: str, *, camera_index: int = 0, frame_cache: Optional[FrameCache] = None
) -> tuple[List[Dict[str, Any]], Path]:
    """
    Convenience helper to capture the latest frame, save it, and build the
    OpenAI content payload for a user turn.
    """
    jpeg_bytes: Optional[bytes] = None
    if frame_cache:
        jpeg_bytes = frame_cache.get_latest_frame(max_age=2.0)

    if jpeg_bytes is None:
        jpeg_bytes = capture_frame(camera_index)

    saved_path = save_frame_to_logs(jpeg_bytes)
    content = build_image_content(message, jpeg_bytes)
    return content, saved_path


