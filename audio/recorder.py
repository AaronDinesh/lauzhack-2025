"""
Utility for press-to-speak audio capture driven by the space bar.
"""

from __future__ import annotations

import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np  # type: ignore
import sounddevice as sd  # type: ignore
import soundfile as sf  # type: ignore
from pynput import keyboard

SAMPLE_RATE = 16_000
CHANNELS = 1


def _wait_for_space_press() -> None:
    """Block until the space bar is pressed."""
    ready = threading.Event()

    def on_press(key: keyboard.Key | keyboard.KeyCode) -> bool:
        if key == keyboard.Key.space:
            ready.set()
            return False
        return True

    with keyboard.Listener(on_press=on_press) as listener:
        ready.wait()
        listener.join()


def _wait_for_space_release() -> None:
    """Block until the space bar is released."""
    released = threading.Event()

    def on_release(key: keyboard.Key | keyboard.KeyCode) -> bool:
        if key == keyboard.Key.space:
            released.set()
            return False
        return True

    listener = keyboard.Listener(on_release=on_release)
    listener.start()
    try:
        while not released.is_set():
            time.sleep(0.05)
    finally:
        listener.stop()
        listener.join()


def _writer_thread(
    file_path: Path, data_queue: "queue.Queue[np.ndarray]", stop_event: threading.Event
) -> None:
    with sf.SoundFile(
        file_path, mode="w", samplerate=SAMPLE_RATE, channels=CHANNELS
    ) as audio_file:
        while not stop_event.is_set() or not data_queue.empty():
            try:
                chunk = data_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            audio_file.write(chunk)


def record_press_to_speak(output_path: Optional[Path] = None) -> Path:
    """
    Wait for the user to hold the space bar, record audio while it's held,
    and persist the capture to a WAV file.
    """
    if output_path is not None:
        destination = output_path
    else:
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        destination = Path(temp_file.name)
        temp_file.close()

    print("Hold SPACE to talk. Release SPACE to stop recording.")
    _wait_for_space_press()

    data_queue: "queue.Queue[np.ndarray]" = queue.Queue()
    stop_event = threading.Event()

    writer = threading.Thread(
        target=_writer_thread, args=(destination, data_queue, stop_event), daemon=True
    )
    writer.start()

    def callback(indata, frames, time_info, status):  # type: ignore[no-untyped-def]
        if status:
            print(f"Audio warning: {status}")
        data_queue.put(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32", callback=callback
    ):
        _wait_for_space_release()

    stop_event.set()
    writer.join()
    return destination


