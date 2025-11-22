"""
Shared camera utilities for capturing frames, persisting screenshots, and
preparing OpenAI-ready content blocks.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import cv2  # type: ignore

LOGS_DIR = Path(__file__).resolve().parents[1] / "logs"


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
    message: str, *, camera_index: int = 0
) -> tuple[List[Dict[str, Any]], Path]:
    """
    Convenience helper to capture the latest frame, save it, and build the
    OpenAI content payload for a user turn.
    """
    jpeg_bytes = capture_frame(camera_index)
    saved_path = save_frame_to_logs(jpeg_bytes)
    content = build_image_content(message, jpeg_bytes)
    return content, saved_path


