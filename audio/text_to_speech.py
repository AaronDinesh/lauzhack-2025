import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from elevenlabs import save  # optional, for saving to file
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")


async def tts_async(
    text: str,
    voice_id: str,
    *,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
    output_path: Optional[str] = None,
):
    """
    Async Text-to-Speech using ElevenLabs SDK.

    - `text`: text to synthesize
    - `voice_id`: ElevenLabs voice ID
    - `model_id`: TTS model (multilingual by default)
    - `output_format`: see ElevenLabs docs (e.g. mp3_44100_128, pcm_16000, ...)
    - `output_path`: if provided, audio is saved to this file (e.g. 'output.mp3')

    Returns:
        `audio` object from ElevenLabs (bytes or iterable of bytes, compatible with `play` and `save`).
    """

    def _sync_call():
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id=model_id,
            text=text,
            output_format=output_format,
        )

        if output_path is not None:
            # save() works with bytes or streaming responses
            save(audio, output_path)

        return play(audio)

    return await asyncio.to_thread(_sync_call)


def speak(
    text: str,
    *,
    voice_id: Optional[str] = None,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
    output_path: Optional[str] = None,
) -> None:
    """Blocking helper that plays TTS audio immediately."""
    resolved_voice = voice_id or DEFAULT_VOICE_ID
    if not resolved_voice:
        raise RuntimeError(
            "No ElevenLabs voice configured. Set ELEVENLABS_VOICE_ID or pass voice_id."
        )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("speak() cannot be used inside an active asyncio loop.")

    asyncio.run(
        tts_async(
            text,
            resolved_voice,
            model_id=model_id,
            output_format=output_format,
            output_path=output_path,
        )
    )
