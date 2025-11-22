# stt_async_sdk.py
import os
import asyncio
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from io import BytesIO

load_dotenv()  # loads ELEVENLABS_API_KEY from .env
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))



async def transcribe_file(audio: str | BytesIO) -> str:
    """
    Async STT using the ElevenLabs SDK.
    Accepts either:
      - a file path (str)
      - a BytesIO MP3 buffer returned by your convert_to_mp3_async function
    Uses asyncio.to_thread to avoid blocking the event loop.
    """

    def _sync_call() -> str:
        if isinstance(audio, str):
            # Case 1: audio is a file path
            with open(audio, "rb") as f:
                result = client.speech_to_text.convert(
                    file=f,
                    model_id="scribe_v1",
                    language_code="eng",
                    diarize=True,
                    tag_audio_events=False,
                    timestamps_granularity="word",
                )
        else:
            # Case 2: audio is a BytesIO buffer
            audio.seek(0)
            result = client.speech_to_text.convert(
                file=audio,
                model_id="scribe_v1",
                language_code="eng",
                diarize=True,
                tag_audio_events=False,
                timestamps_granularity="word",
            )

        return result.text

    return await asyncio.to_thread(_sync_call)

# Example usage
async def main():
    text = await transcribe_file("test.m4a")
    print(text)

if __name__ == "__main__":
    asyncio.run(main())
