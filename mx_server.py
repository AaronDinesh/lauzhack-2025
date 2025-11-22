import os
import sys
import threading
from pathlib import Path
from time import perf_counter
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

from audio.recorder import ContinuousRecorder
from audio.speech_to_text import transcribe_file_sync
from audio.text_to_speech import speak_text
from camera.helpers import FrameCache, capture_with_context

load_dotenv()

app = FastAPI(title="Jarvis Backend")

class ConsoleAction(BaseModel):
    action: str
    value: Optional[int] = None

state: Dict[str, Any] = {
    "mode": "idle",
    "components": [],      # filled after scan
    "resource_slots": {},  # maps "resource_1" -> {"label", "icon", "url", ...}
    "current_recording": None,
    "last_recording": None,
    "talk_recording_active": False,
    "last_transcript": None,
    "last_response": None,
}

MODEL_NAME = os.getenv("JARVIS_RESPONSES_MODEL", "gpt-5-nano")
VOICE_PRESET = os.getenv("OPENAI_TTS_VOICE", "alloy")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
REASONING_EFFORT = os.getenv("JARVIS_REASONING_EFFORT", "minimal")
SYSTEM_PROMPT = os.getenv(
    "JARVIS_SYSTEM_PROMPT",
    "You are a friendly assistant that describes what you see and converses naturally.",
)
EXIT_PHRASES = {
    phrase.strip().lower()
    for phrase in os.getenv("JARVIS_EXIT_PHRASES", "quit,exit,goodbye").split(",")
    if phrase.strip()
}
CAMERA_INDEX = int(os.getenv("JARVIS_CAMERA_INDEX", "0"))
FRAME_REFRESH = float(os.getenv("FRAME_CACHE_REFRESH", "0.5"))

client = OpenAI()

conversation: List[Dict[str, Any]] = []
if SYSTEM_PROMPT:
    conversation.append(
        {
            "role": "system",
            "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
        }
    )

frame_cache: FrameCache | None = None


def _extract_first_text(response_dict: Dict[str, Any]) -> str:
    outputs = response_dict.get("output", [])
    for item in outputs:
        for chunk in item.get("content", []):
            if chunk.get("type") == "output_text":
                return chunk.get("text", "").strip()
    return ""


def _log_step_duration(step_name: str, start_time: float) -> float:
    elapsed = perf_counter() - start_time
    print(f"[Pipeline] {step_name} took {elapsed:.2f}s")
    return perf_counter()


def _stream_assistant_text(
    conversation_history: List[Dict[str, Any]],
) -> str:
    request_kwargs: Dict[str, Any] = {
        "model": MODEL_NAME,
        "input": conversation_history,
    }
    if REASONING_EFFORT:
        request_kwargs["reasoning"] = {"effort": REASONING_EFFORT}

    text_chunks: List[str] = []
    final_response: Any | None = None

    with client.responses.stream(**request_kwargs) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                text_chunks.append(event.delta)
            elif event.type == "response.error":
                error = getattr(event, "error", None)
                message = "OpenAI streaming error"
                if isinstance(error, dict):
                    message = error.get("message") or message
                raise RuntimeError(message)

        final_response = stream.get_final_response()

    assistant_text = "".join(text_chunks).strip()
    if assistant_text:
        return assistant_text

    response_dict: Dict[str, Any] = {}
    if final_response is not None:
        if hasattr(final_response, "model_dump"):
            response_dict = final_response.model_dump()  # type: ignore[assignment]
        elif hasattr(final_response, "to_dict"):
            response_dict = final_response.to_dict()  # type: ignore[assignment]

    return _extract_first_text(response_dict)


def _process_recording(audio_path: Path) -> Dict[str, Any]:
    step_start = perf_counter()
    transcript = ""
    try:
        transcript = transcribe_file_sync(str(audio_path)).strip()
    except Exception as exc:
        return {"status": "error", "error": f"Transcription failed: {exc}"}
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass

    step_start = _log_step_duration("transcribe_file_sync", step_start)

    if not transcript:
        return {"status": "error", "error": "Silence detected or unable to transcribe."}

    print(f"[User] {transcript}")
    if transcript.lower() in EXIT_PHRASES:
        return {"status": "ok", "transcript": transcript, "message": "Exit phrase detected."}

    try:
        content, screenshot_path = capture_with_context(
            transcript,
            camera_index=CAMERA_INDEX,
            frame_cache=frame_cache,
        )
        step_start = _log_step_duration("capture_with_context", step_start)
        print(f"[Pipeline] Captured screenshot at {screenshot_path}")
    except Exception as exc:
        return {
            "status": "error",
            "error": f"Camera capture failed: {exc}",
            "transcript": transcript,
        }

    conversation.append({"role": "user", "content": content})

    try:
        assistant_text = _stream_assistant_text(conversation)
        step_start = _log_step_duration("responses.stream", step_start)
    except Exception as exc:
        conversation.pop()  # remove the failed user turn
        return {
            "status": "error",
            "error": f"Assistant streaming failed: {exc}",
            "transcript": transcript,
        }

    if not assistant_text:
        return {
            "status": "error",
            "error": "Assistant returned no text output.",
            "transcript": transcript,
        }

    print(f"[Assistant] {assistant_text}")
    conversation.append(
        {
            "role": "assistant",
            "content": [{"type": "output_text", "text": assistant_text}],
        }
    )

    tts_error = None
    try:
        speak_text(
            client,
            assistant_text,
            voice=VOICE_PRESET,
            model=TTS_MODEL,
        )
    except Exception as exc:
        tts_error = str(exc)
    finally:
        _log_step_duration("audio.playback", step_start)

    result: Dict[str, Any] = {
        "status": "ok",
        "transcript": transcript,
        "assistant_text": assistant_text,
        "screenshot_path": screenshot_path,
    }
    if tts_error:
        result["tts_error"] = tts_error
    return result


@app.on_event("startup")
def _startup() -> None:
    global frame_cache
    try:
        frame_cache = FrameCache(camera_index=CAMERA_INDEX, refresh_interval=FRAME_REFRESH)
        frame_cache.start()
        frame_cache.wait_until_ready(timeout=3.0)
        print("[Startup] Frame cache initialized")
    except Exception as exc:
        print(f"Frame cache unavailable: {exc}", file=sys.stderr)
        if frame_cache:
            frame_cache.stop()
            frame_cache = None


@app.on_event("shutdown")
def _shutdown() -> None:
    if frame_cache:
        frame_cache.stop()


class RecordingController:
    """
    Lightweight thread-safe wrapper around ContinuousRecorder for the server.
    """

    def __init__(self) -> None:
        self._recorder = ContinuousRecorder()
        self._lock = threading.Lock()
        self._current_path: Optional[Path] = None

    def start(self, output_path: Optional[Path] = None) -> Path:
        with self._lock:
            if self._recorder.is_recording():
                raise RuntimeError("Recording already in progress")
            self._current_path = self._recorder.start(output_path)
            return self._current_path

    def stop(self) -> Path:
        with self._lock:
            if not self._recorder.is_recording() or self._current_path is None:
                raise RuntimeError("No recording in progress")
            destination = self._recorder.stop()
            self._current_path = None
            return destination

    def is_recording(self) -> bool:
        with self._lock:
            return self._recorder.is_recording()

    def current_path(self) -> Optional[Path]:
        with self._lock:
            return self._current_path


talk_recorder = RecordingController()


def recording_status() -> Dict[str, Any]:
    current = talk_recorder.current_path()
    return {
        "recording": talk_recorder.is_recording(),
        "path": str(current) if current else None,
    }


# Fake "VLM" / LLM pipeline 

def fake_llm_analyse_scene() -> Dict[str, Any]:
    # hardcdoded analysis result

    components = [
        {
            "name": "ASUS Prime Motherboard",
            "type": "motherboard",
            "manual_url": "https://example.com/asus_prime_manual.pdf",
            "video_url": "https://www.youtube.com/embed/VIDEO_ID_MOBO",
        },
        {
            "name": "Corsair DDR4 RAM",
            "type": "ram",
            "manual_url": "https://example.com/corsair_ddr4_manual.pdf",
            "video_url": "https://www.youtube.com/embed/VIDEO_ID_RAM",
        },
    ]

    # Choose what we want on the three resource keys.
    resource_slots = {
        "resource_1": {
            "label": "Mobo manual",
            "icon": "motherboard",  # maps to motherboard.png in plugin
            "url": components[0]["manual_url"],
        },
        "resource_2": {
            "label": "RAM manual",
            "icon": "ram",
            "url": components[1]["manual_url"],
        },
        "resource_3": {
            "label": "RAM video",
            "icon": "video",
            "url": components[1]["video_url"],
        },
    }

    return {"components": components, "resource_slots": resource_slots}


# Routes

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/console/action")
def handle_console_action(action: ConsoleAction):
    """
    Main entrypoint for the MX plugin.

    Actions we handle:
      - "scan"         : user pressed the Scan button
      - "talk"         : user wants to start talking to Jarvis
      - "resource_1/2/3": user pressed a resource key
      - "scroll_component": dial rotated (for later use)
    """
    print("Received console action:", action)

    if action.action == "scan":
        #pretend to analyse scene with a VLM/LLM
        result = fake_llm_analyse_scene()
        state["mode"] = "scanned"
        state["components"] = result["components"]
        state["resource_slots"] = result["resource_slots"]

        # build button updates for plugin
        buttons: List[Dict[str, Any]] = []
        for slot, cfg in state["resource_slots"].items():
            buttons.append(
                {
                    "slot": slot,        # "resource_1", "resource_2", ...
                    "label": cfg["label"],
                    "icon": cfg["icon"],  # e.g. "ram" -> ram.png
                }
            )

        summary = (
            "I see an ASUS Prime motherboard and Corsair DDR4 RAM. "
            "How would you like to proceed?"
        )

        return {
            "status": "ok",
            "mode": state["mode"],
            "message": summary,
            "buttons": buttons,
        }

    elif action.action == "talk":
        if not state["talk_recording_active"]:
            try:
                path = talk_recorder.start()
            except Exception as exc:  # noqa: BLE001
                return {
                    "status": "error",
                    "error": f"Failed to start talk recording: {exc}",
                    "recording": recording_status(),
                }

            state["mode"] = "talking"
            state["talk_recording_active"] = True
            state["current_recording"] = str(path)
            return {
                "status": "ok",
                "mode": state["mode"],
                "message": (
                    "Jarvis is listening. Ask what you want to do with the "
                    "motherboard or RAM."
                ),
                "recording": recording_status(),
            }

        try:
            path = talk_recorder.stop()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "error": f"Failed to stop talk recording: {exc}",
                "recording": recording_status(),
            }

        processing = _process_recording(Path(path))

        state["mode"] = "idle"
        state["talk_recording_active"] = False
        state["last_recording"] = str(path)
        state["current_recording"] = None
        state["last_transcript"] = processing.get("transcript")
        state["last_response"] = processing.get("assistant_text")

        response_payload = {
            "status": processing.get("status", "ok"),
            "mode": state["mode"],
            "message": "Jarvis stopped listening.",
            "recording": {"recording": False, "path": str(path)},
        }
        response_payload.update(processing)
        return response_payload

    elif action.action.startswith("resource_"):
        slot = action.action  # "resource_1", "resource_2", ...
        resource = state["resource_slots"].get(slot)

        if not resource:
            return {"status": "error", "error": f"no resource mapped for {slot}"}

        # Frontend / launcher can use this URL to open manual / video / file.
        return {
            "status": "ok",
            "mode": state["mode"],
            "slot": slot,
            "label": resource["label"],
            "icon": resource["icon"],
            "url": resource["url"],
        }

    elif action.action == "scroll_component":
        # dial rotation – your UI can use this later to move selection
        return {
            "status": "ok",
            "mode": state["mode"],
            "note": f"scroll tick={action.value}",
        }

    # Fallback
    return {"status": "ok", "mode": state["mode"]}
