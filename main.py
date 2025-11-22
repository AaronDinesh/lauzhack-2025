from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from audio.recorder import record_press_to_speak
from audio.speech_to_text import transcribe_file_sync
from audio.text_to_speech import speak
from camera.helpers import capture_with_context


def _extract_first_text(response_dict: Dict[str, Any]) -> str:
    outputs = response_dict.get("output", [])
    for item in outputs:
        for chunk in item.get("content", []):
            if chunk.get("type") == "output_text":
                return chunk.get("text", "").strip()
    return ""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Press-to-speak multimodal chat with OpenAI + ElevenLabs."
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI Responses model to use.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Camera index for screenshots.",
    )
    parser.add_argument(
        "--voice-id",
        default=os.getenv("ELEVENLABS_VOICE_ID"),
        help="Override ElevenLabs voice ID.",
    )
    parser.add_argument(
        "--exit-phrases",
        nargs="*",
        default=["quit", "exit", "goodbye"],
        help="Phrases that will end the conversation when spoken.",
    )
    parser.add_argument(
        "--system-prompt",
        default="You are a friendly assistant that describes what you see and converses naturally.",
        help="Optional system prompt to control assistant behavior.",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = _build_parser().parse_args()

    client = OpenAI()
    exit_phrases = {phrase.lower() for phrase in args.exit_phrases}

    conversation: List[Dict[str, Any]] = []
    if args.system_prompt:
        conversation.append(
            {
                "role": "system",
                "content": [{"type": "input_text", "text": args.system_prompt}],
            }
        )

    print("Conversation ready. Hold SPACE to speak; release to send. Say 'quit' to exit.")

    while True:
        try:
            audio_path = record_press_to_speak()
        except KeyboardInterrupt:
            print("\nInterrupted while waiting for input. Exiting.")
            break
        except Exception as exc:
            print(f"Failed to capture audio: {exc}", file=sys.stderr)
            continue

        transcript = ""
        try:
            transcript = transcribe_file_sync(str(audio_path)).strip()
        except Exception as exc:
            print(f"Transcription failed: {exc}", file=sys.stderr)
        finally:
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

        if not transcript:
            print("Heard silence or could not transcribe. Please try again.")
            continue

        print(f"You: {transcript}")
        if transcript.lower() in exit_phrases:
            print("Exit phrase detected. Goodbye!")
            break

        try:
            content, screenshot_path = capture_with_context(
                transcript, camera_index=args.camera_index
            )
            print(f"Captured screenshot at {screenshot_path}")
        except Exception as exc:
            print(f"Camera capture failed: {exc}", file=sys.stderr)
            continue

        conversation.append({"role": "user", "content": content})

        try:
            response = client.responses.create(model=args.model, input=conversation)
            response_dict = response.to_dict()  # type: ignore[assignment]
        except Exception as exc:
            print(f"OpenAI request failed: {exc}", file=sys.stderr)
            conversation.pop()
            continue

        assistant_text = _extract_first_text(response_dict)
        if not assistant_text:
            print("Assistant returned no text output.", file=sys.stderr)
            continue

        print(f"Assistant: {assistant_text}")
        conversation.append(
            {
                "role": "assistant",
                "content": [{"type": "output_text", "text": assistant_text}],
            }
        )

        try:
            speak(assistant_text, voice_id=args.voice_id)
        except Exception as exc:
            print(f"Unable to play TTS: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

