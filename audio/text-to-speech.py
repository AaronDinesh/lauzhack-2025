import asyncio
import os
from typing import Optional
from elevenlabs.client import ElevenLabs
from elevenlabs import save  # optional, for saving to file
from dotenv import load_dotenv
from elevenlabs.play import play

load_dotenv() 
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

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



async def main():
    await tts_async(
        "Hello from ElevenLabs async TTS!",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        output_path="output.mp3"
    )

if __name__ == "__main__":
    asyncio.run(main())
