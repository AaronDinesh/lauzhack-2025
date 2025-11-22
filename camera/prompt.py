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
import sys
from typing import Any, Dict

from dotenv import load_dotenv  # type: ignore
from openai import OpenAI

from .helpers import capture_with_context

# Load variables from .env if present so OPENAI_API_KEY is available.
load_dotenv()


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
    content, saved_path = capture_with_context(message, camera_index=camera_index)
    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": content}],
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

