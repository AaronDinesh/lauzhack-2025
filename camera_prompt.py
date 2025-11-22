#!/usr/bin/env python3
"""
Capture a single webcam frame, save it under logs/, and send it along
with a text prompt to the OpenAI Responses API.

Requirements:
  pip install opencv-python openai python-dotenv

Environment:
  OPENAI_API_KEY must be set before running the script.
"""

from __future__ import annotations

import argparse
import base64
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import cv2  # type: ignore
from dotenv import load_dotenv  # type: ignore
from openai import OpenAI


LOGS_DIR = Path(__file__).resolve().parent / "logs"

# Load variables from .env if present so OPENAI_API_KEY is available.
load_dotenv()


def _capture_frame(camera_index: int) -> bytes:
    """Capture one frame from the given camera index and return JPEG bytes."""
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


def _jpeg_bytes_to_data_url(jpeg_bytes: bytes) -> str:
    """Convert JPEG bytes to a data URL string for the OpenAI API."""
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _save_frame_to_logs(jpeg_bytes: bytes, logs_dir: Path = LOGS_DIR) -> Path:
    """Persist the captured frame into the logs directory."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = logs_dir / f"screenshot-{timestamp}.jpg"
    destination.write_bytes(jpeg_bytes)
    return destination


def send_message_with_camera(
    message: str,
    *,
    camera_index: int = 0,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """
    Send a text message along with the current camera frame to OpenAI.

    Returns the full response dictionary for maximum flexibility.
    """
    jpeg_bytes = _capture_frame(camera_index)
    saved_path = _save_frame_to_logs(jpeg_bytes)
    image_url = _jpeg_bytes_to_data_url(jpeg_bytes)

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": message},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
    )
    print(f"Saved screenshot to {saved_path}", file=sys.stderr)
    return response.to_dict()  # type: ignore[no-any-return]


def _pretty_print_response(response: Dict[str, Any]) -> None:
    """Best-effort extraction of the first text output for convenience."""
    outputs = response.get("output", [])
    for item in outputs:
        if "content" not in item:
            continue
        for chunk in item["content"]:
            if chunk.get("type") == "output_text":
                print(chunk.get("text", "").strip())
                return
    print(response)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a prompt and current camera frame to OpenAI."
    )
    parser.add_argument(
        "--message",
        "-m",
        default="what do you see",
        help="Text to send alongside the camera frame (default: %(default)s)",
    )
    parser.add_argument(
        "--camera-index",
        "-c",
        type=int,
        default=0,
        help="Index of the camera to use (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to target (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        response = send_message_with_camera(
            args.message, camera_index=args.camera_index, model=args.model
        )
    except Exception as exc:  # pragma: no cover - user convenience
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    _pretty_print_response(response)


if __name__ == "__main__":
    main()

