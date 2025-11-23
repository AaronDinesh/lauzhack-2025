#!/usr/bin/env python3
"""
Quick utility to enumerate connected cameras and preview a live feed.

Requirements:
  pip install opencv-python
"""

from __future__ import annotations

import argparse
import sys
from typing import List

import cv2  # type: ignore
from dotenv import load_dotenv

load_dotenv()


def list_cameras(max_index: int) -> List[int]:
    """Return indices of cameras that respond to cv2.VideoCapture."""
    available: List[int] = []
    for idx in range(max_index + 1):
        capture = cv2.VideoCapture(idx)
        if capture.isOpened():
            available.append(idx)
        capture.release()
    return available


def show_stream(camera_index: int) -> None:
    """Display a continuous camera preview until the user quits."""
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open camera at index {camera_index}")

    print(
        "Streaming from camera index "
        f"{camera_index}. Press 'q' or ESC in the preview window to exit."
    )

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Failed to read frame; camera may have disconnected.")
            cv2.imshow("Camera Preview", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # 27 = ESC
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="List connected cameras and preview a live feed.")
    parser.add_argument(
        "--max-index",
        type=int,
        default=5,
        help="Highest camera index to probe when listing (default: %(default)s)",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Camera index to preview (default: %(default)s)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list cameras; skip starting the preview window.",
    )
    args = parser.parse_args()

    available = list_cameras(args.max_index)
    if available:
        print(f"Detected cameras: {', '.join(map(str, available))}")
    else:
        print(
            f"No cameras responded in range 0..{args.max_index}. "
            "Adjust --max-index or check connections."
        )

    if args.list_only:
        return

    if available and args.camera_index not in available:
        print(
            f"Warning: camera index {args.camera_index} was not detected; attempting anyway.",
            file=sys.stderr,
        )

    try:
        show_stream(args.camera_index)
    except Exception as exc:  # pragma: no cover - user convenience
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
