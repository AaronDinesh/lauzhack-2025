from __future__ import annotations

import os
import threading
from io import BytesIO

import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
DEFAULT_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
DEFAULT_TTS_FORMAT = os.getenv("OPENAI_TTS_FORMAT", "pcm")
DEFAULT_TTS_SAMPLE_RATE = int(os.getenv("OPENAI_TTS_SAMPLE_RATE", "24000"))

# Global flag to signal TTS interruption
_stop_tts_event = threading.Event()
_tts_lock = threading.Lock()


def stop_speech() -> None:
    """Stop any ongoing TTS playback."""
    global _stop_tts_event
    _stop_tts_event.set()
    sd.stop()  # Stop all sounddevice playback immediately


def reset_stop_flag() -> None:
    """Reset the stop flag before starting new TTS."""
    global _stop_tts_event
    _stop_tts_event.clear()


def speak_text(
    client: OpenAI,
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
    response_format: str | None = None,
) -> None:
    """
    Render TTS audio with the lowest possible latency.
    Streams PCM directly to the sound device; falls back to buffered playback for other formats.
    Can be interrupted by calling stop_speech().
    """
    with _tts_lock:
        reset_stop_flag()
        
        fmt = (response_format or DEFAULT_TTS_FORMAT or "pcm").lower()
        if fmt == "pcm":
            _stream_pcm_to_device(client, text, voice=voice, model=model)
            return

        audio_bytes = synthesize_speech(client, text, voice=voice, model=model, response_format=fmt)
        play_audio(audio_bytes)


def synthesize_speech(
    client: OpenAI,
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
    response_format: str | None = None,
) -> bytes:
    """Buffer the entire audio (non-streaming formats)."""

    model_name = model or DEFAULT_TTS_MODEL
    voice_name = voice or DEFAULT_TTS_VOICE or "alloy"
    fmt = response_format or DEFAULT_TTS_FORMAT or "wav"

    if not model_name:
        raise RuntimeError(
            "No OpenAI TTS model configured. "
            "Set OPENAI_TTS_MODEL or pass --tts-model."
        )

    audio_buffer = bytearray()
    with client.audio.speech.with_streaming_response.create(
        model=model_name,
        voice=voice_name,
        response_format=fmt,
        input=text,
        stream_format="audio",
    ) as speech_stream:
        for chunk in speech_stream.iter_bytes():
            audio_buffer.extend(chunk)

    return bytes(audio_buffer)


def play_audio(audio_bytes: bytes) -> None:
    """Play a WAV/AIFF byte-stream via sounddevice. Can be interrupted."""
    if not audio_bytes or _stop_tts_event.is_set():
        return

    with sf.SoundFile(BytesIO(audio_bytes)) as audio_file:
        samples = audio_file.read(dtype="float32")
        sd.play(samples, audio_file.samplerate)
        
        # Wait with interruption check (poll every 100ms)
        while True:
            if _stop_tts_event.is_set():
                sd.stop()
                return
            try:
                if not sd.get_stream().active:
                    break
            except (sd.PortAudioError, AttributeError):
                # Stream finished or no active stream
                break
            sd.sleep(100)  # Check every 100ms


def _stream_pcm_to_device(
    client: OpenAI,
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
) -> None:
    """Request PCM output and push chunks to the audio device as they arrive. Can be interrupted."""

    model_name = model or DEFAULT_TTS_MODEL
    voice_name = voice or DEFAULT_TTS_VOICE or "alloy"
    if not model_name:
        raise RuntimeError(
            "No OpenAI TTS model configured. "
            "Set OPENAI_TTS_MODEL or pass --tts-model."
        )

    with sd.RawOutputStream(
        samplerate=DEFAULT_TTS_SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=0,
    ) as audio_stream:
        leftover = b""
        with client.audio.speech.with_streaming_response.create(
            model=model_name,
            voice=voice_name,
            response_format="pcm",
            input=text,
            stream_format="audio",
        ) as speech_stream:
            for chunk in speech_stream.iter_bytes():
                # Check if we should stop
                if _stop_tts_event.is_set():
                    return
                
                if chunk:
                    if leftover:
                        chunk = leftover + chunk
                        leftover = b""

                    size = len(chunk)
                    remainder = size % 2
                    if remainder:
                        playable = chunk[:-remainder]
                        leftover = chunk[-remainder:]
                    else:
                        playable = chunk

                    if playable:
                        audio_stream.write(playable)

        # Final check before writing leftover
        if _stop_tts_event.is_set():
            return
            
        if leftover:
            # pad the final byte and write it
            padded = leftover + b"\x00" * (2 - len(leftover))
            audio_stream.write(padded)

    # Wait with interruption check (poll every 100ms)
    while True:
        if _stop_tts_event.is_set():
            sd.stop()
            return
        try:
            if not sd.get_stream().active:
                break
        except (sd.PortAudioError, AttributeError):
            # Stream finished or no active stream
            break
        sd.sleep(100)  # Check every 100ms
