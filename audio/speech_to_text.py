from __future__ import annotations

import asyncio
import os
from io import BytesIO
from typing import IO, Union

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

AudioSource = Union[str, BytesIO]
DEFAULT_TRANSCRIPTION_MODEL = os.getenv(
    "OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
)
DEFAULT_TRANSCRIPTION_LANGUAGE = os.getenv("OPENAI_TRANSCRIPTION_LANGUAGE", "en")


class _OpenAITranscriber:
    """Lazily constructs the OpenAI client to avoid import-time failures."""

    _client: OpenAI | None = None

    @classmethod
    def client(cls) -> OpenAI:
        if cls._client is None:
            cls._client = OpenAI()
        return cls._client


async def transcribe_file(
    audio: AudioSource, *, model: str | None = None, language: str | None = None
) -> str:
    """
    Async STT using OpenAI's /audio/transcriptions endpoint.
    Accepts either a filesystem path or a BytesIO buffer.
    """

    model_name = model or DEFAULT_TRANSCRIPTION_MODEL
    if not model_name:
        raise RuntimeError(
            "No OpenAI transcription model configured. "
            "Set OPENAI_TRANSCRIPTION_MODEL or pass model explicitly."
        )
    lang = language or DEFAULT_TRANSCRIPTION_LANGUAGE or "en"

    def _call_api(handle: IO[bytes]) -> str:
        response = _OpenAITranscriber.client().audio.transcriptions.create(
            model=model_name,
            file=handle,
            language=lang,
        )
        text = getattr(response, "text", "")
        return text.strip()

    def _sync_call() -> str:
        if isinstance(audio, str):
            with open(audio, "rb") as file_handle:
                return _call_api(file_handle)

        audio.seek(0)
        return _call_api(audio)

    return await asyncio.to_thread(_sync_call)


def transcribe_file_sync(
    audio: AudioSource, *, model: str | None = None, language: str | None = None
) -> str:
    """Convenience wrapper to transcribe without dealing with asyncio."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "transcribe_file_sync cannot run inside an existing asyncio loop."
        )

    return asyncio.run(transcribe_file(audio, model=model, language=language))
