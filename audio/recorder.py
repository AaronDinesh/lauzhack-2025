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


class ContinuousRecorder:
    """
    Programmatic audio recorder that can be started and stopped via API calls.
    """

    def __init__(self, *, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self._sample_rate = sample_rate
        self._channels = channels
        self._data_queue: "queue.Queue[np.ndarray]" | None = None
        self._stop_event = threading.Event()
        self._writer: threading.Thread | None = None
        self._stream: sd.InputStream | None = None
        self._destination: Path | None = None
        self._lock = threading.Lock()

    def start(self, output_path: Optional[Path] = None) -> Path:
        """
        Start capturing audio until stop() is invoked. Returns the output path.
        """
        with self._lock:
            if self._stream is not None:
                raise RuntimeError("Recording already in progress")

            self._destination = self._resolve_destination(output_path)
            self._data_queue = queue.Queue()
            self._stop_event.clear()

            self._writer = threading.Thread(
                target=_writer_thread,
                args=(self._destination, self._data_queue, self._stop_event),
                daemon=True,
            )
            self._writer.start()

            def callback(indata, frames, time_info, status):  # type: ignore[no-untyped-def]
                if status:
                    print(f"Audio warning: {status}")
                if self._data_queue is not None:
                    self._data_queue.put(indata.copy())

            try:
                self._stream = sd.InputStream(
                    samplerate=self._sample_rate,
                    channels=self._channels,
                    dtype="float32",
                    callback=callback,
                )
                self._stream.start()
            except Exception:
                self._stop_event.set()
                if self._writer:
                    self._writer.join()
                self._cleanup_failed_start()
                raise

            return self._destination

    def stop(self) -> Path:
        """
        Stop the recording and return the path to the captured WAV file.
        """
        with self._lock:
            if self._stream is None or self._destination is None:
                raise RuntimeError("No recording in progress")

            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._stop_event.set()
        if self._writer:
            self._writer.join()
        self._writer = None
        self._data_queue = None
        destination = self._destination
        self._destination = None
        return destination

    def is_recording(self) -> bool:
        return self._stream is not None

    def _resolve_destination(self, output_path: Optional[Path]) -> Path:
        if output_path is not None:
            return output_path
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        destination = Path(temp_file.name)
        temp_file.close()
        return destination

    def _cleanup_failed_start(self) -> None:
        if self._destination:
            try:
                self._destination.unlink(missing_ok=True)
            except Exception:
                pass
        self._destination = None
        self._data_queue = None
        self._writer = None
        self._stream = None
        self._stop_event.set()

