from __future__ import annotations

import math
from typing import Final

import numpy as np
import sounddevice as sd

DEFAULT_SAMPLE_RATE: Final[int] = 24000
DEFAULT_VOLUME: Final[float] = 0.25


def _build_tone(frequency: float, duration: float, sample_rate: int) -> np.ndarray:
    """Return a dampened sine tone."""
    total_samples = max(int(duration * sample_rate), 1)
    times = np.linspace(0, duration, total_samples, endpoint=False)
    envelope = np.exp(-3.5 * times)
    samples = DEFAULT_VOLUME * np.sin(2 * math.pi * frequency * times) * envelope
    return samples.astype(np.float32)


def play_tool_complete_sound(
    duration: float = 0.35,
    *,
    frequency: float = 1046.5,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """
    Play a short chime to signal that asynchronous tool execution finished.
    Safe to call from a background thread.
    """
    try:
        tone = _build_tone(frequency, duration, sample_rate)
        sd.play(tone, sample_rate)
        sd.wait()
    except Exception as exc:  # noqa: BLE001
        print(f"[Audio] Failed to play tool-complete sound: {exc}")

