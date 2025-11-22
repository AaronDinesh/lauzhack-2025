from __future__ import annotations

import os
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
    """

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
    """Play a WAV/AIFF byte-stream via sounddevice."""
    if not audio_bytes:
        return

    with sf.SoundFile(BytesIO(audio_bytes)) as audio_file:
        samples = audio_file.read(dtype="float32")
        sd.play(samples, audio_file.samplerate)
        sd.wait()


def _stream_pcm_to_device(
    client: OpenAI,
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
) -> None:
    """Request PCM output and push chunks to the audio device as they arrive."""

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

        if leftover:
            # pad the final byte and write it
            padded = leftover + b"\x00" * (2 - len(leftover))
            audio_stream.write(padded)

    sd.wait()
