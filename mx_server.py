import json
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
from audio.text_to_speech import speak_text, stop_speech
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
_tts_thread_lock = threading.Lock()
_active_tts_thread: threading.Thread | None = None


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


def _play_response_async(text: str) -> None:
    """Spawn a background thread for TTS so the endpoint can return immediately."""
    global _active_tts_thread

    def _tts_worker() -> None:
        global _active_tts_thread
        step_start = perf_counter()
        try:
            speak_text(
                client,
                text,
                voice=VOICE_PRESET,
                model=TTS_MODEL,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[TTS] playback failed: {exc}", file=sys.stderr)
        finally:
            _log_step_duration("audio.playback", step_start)
            with _tts_thread_lock:
                if threading.current_thread() is _active_tts_thread:
                    _active_tts_thread = None

    thread = threading.Thread(target=_tts_worker, name="tts-playback", daemon=True)
    with _tts_thread_lock:
        _active_tts_thread = thread
    thread.start()


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
        _play_response_async(assistant_text)
    except Exception as exc:
        tts_error = str(exc)
    finally:
        # Each playback thread logs its own duration, so nothing to do here.
        pass

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
def analyse_scene_with_vlm_stub() -> Dict[str, Any]:
    """
    Stand-in for the real VLM pipeline.
    Returns detected components and resource slot metadata.
    """

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


def _build_buttons_from_state(resource_slots: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return runtime button metadata for future dynamic icon updates."""
    buttons: List[Dict[str, Any]] = []
    for slot, cfg in resource_slots.items():
        buttons.append(
            {
                "slot": slot,
                "label": cfg["label"],
                "icon": cfg["icon"],
            }
        )
    return buttons


def _extract_json_from_response(resp: Any) -> Dict[str, Any]:
    """Parse JSON text from OpenAI Responses result."""
    try:
        if hasattr(resp, "output"):
            outputs = resp.output or []
        elif isinstance(resp, dict):
            outputs = resp.get("output", [])
        else:
            outputs = []

        for item in outputs:
            for chunk in item.get("content", []):
                if chunk.get("type") == "output_text":
                    text = (chunk.get("text") or "").strip()
                    if text:
                        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        print(f"[VLM] Failed to parse JSON: {exc}", file=sys.stderr)
    return {}


def analyse_scene_with_vlm() -> Dict[str, Any]:
    """
    Real VLM call: capture a frame and ask the model for structured components/resources.
    Falls back to stub on failure.
    """
    if frame_cache is None:
        print("[VLM] Frame cache not initialized; falling back to stub", file=sys.stderr)
        return analyse_scene_with_vlm_stub()

    # Capture image + recent conversation context; description drives the vision call.
    content, screenshot_path = capture_with_context(
        "Identify visible PC components and propose manuals/videos.",
        camera_index=CAMERA_INDEX,
        frame_cache=frame_cache,
    )
    print(f"[VLM] Captured screenshot for analysis at {screenshot_path}")

    schema = {
        "name": "scene_analysis",
        "schema": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "manual_url": {"type": "string"},
                            "video_url": {"type": "string"},
                        },
                        "required": ["name", "type"],
                    },
                },
                "resource_slots": {
                    "type": "object",
                    "patternProperties": {
                        "^resource_[1-3]$": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "icon": {"type": "string"},
                                "url": {"type": "string"},
                            },
                            "required": ["label", "icon", "url"],
                        }
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["components", "resource_slots"],
        },
        "strict": True,
    }

    system_prompt = (
        "You are Jarvis, a PC hardware assistant. Inspect the image and text, "
        "identify the most relevant devices, and map resource slots for a Logitech MX keypad. "
        "You MUST fill resource_1/2/3 with concise labels (emoji allowed), icons, and real URLs "
        "to manuals/support pages or reputable tutorials (no placeholders). "
        "Prefer: resource_1 = primary device manual; resource_2 = secondary device manual or alternate guide; "
        "resource_3 = video tutorial for the primary device. "
        "Return ONLY JSON matching the provided schema."
    )

    try:
        resp = client.responses.create(
            model=MODEL_NAME,
            response_format={"type": "json_schema", "json_schema": schema},
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": content
                    + [
                        {
                            "type": "input_text",
                            "text": (
                                "Populate resource_1/2/3 with label, icon, url for the keypad. "
                                "You MUST avoid placeholders; pick the closest relevant manual/support page or a reputable tutorial link. "
                                "Keep labels short and keypad-friendly (emoji allowed)."
                            ),
                        }
                    ],
                },
            ],
        )

        parsed = _extract_json_from_response(resp)
        if parsed:
            components = parsed.get("components") or []
            resource_slots = parsed.get("resource_slots") or {}

            # If VLM did not propose resources, derive sensible defaults from components.
            if not resource_slots:
                if components:
                    resource_slots = _build_resource_slots_from_components(components)
                else:
                    # Last resort: stub
                    stub = analyse_scene_with_vlm_stub()
                    components = stub["components"]
                    resource_slots = stub["resource_slots"]

            return {"components": components, "resource_slots": resource_slots}
    except Exception as exc:  # noqa: BLE001
        print(f"[VLM] Analysis failed, will fall back to stub: {exc}", file=sys.stderr)

    return analyse_scene_with_vlm_stub()


def _build_summary_from_components(components: List[Dict[str, Any]]) -> str:
    names = [c.get("name") for c in components if c.get("name")]
    if not names:
        return "I found some components. How would you like to proceed?"
    if len(names) == 1:
        return f"I see {names[0]}. How would you like to proceed?"
    return f"I see {', '.join(names[:-1])} and {names[-1]}. How would you like to proceed?"


def _build_resource_slots_from_components(components: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Derive resource slots from detected components:
      resource_1: manual for first component
      resource_2: manual for second component (or video for first if only one)
      resource_3: video/tutorial for first component
    """
    if not components:
        return {}

    def icon_for(component: Dict[str, Any]) -> str:
        return (component.get("type") or "manual").lower()

    primary = components[0]
    secondary = components[1] if len(components) > 1 else None

    def safe_url(*candidates: str) -> str:
        for c in candidates:
            if c:
                return c
        # Last resort: vendor search link (keeps it non-empty but useful)
        query = primary.get("name") or primary.get("type") or "pc hardware"
        return f"https://www.google.com/search?q={query.replace(' ', '+')}+manual"

    slots: Dict[str, Dict[str, Any]] = {}
    slots["resource_1"] = {
        "label": f"{primary.get('name', 'Component')} manual",
        "icon": icon_for(primary),
        "url": safe_url(primary.get("manual_url"), primary.get("url")),
    }

    if secondary:
        slots["resource_2"] = {
            "label": f"{secondary.get('name', 'Component')} manual",
            "icon": icon_for(secondary),
            "url": safe_url(secondary.get("manual_url"), secondary.get("url")),
        }
    else:
        slots["resource_2"] = {
            "label": f"{primary.get('name', 'Component')} manual",
            "icon": icon_for(primary),
            "url": safe_url(primary.get("manual_url"), primary.get("url")),
        }

    slots["resource_3"] = {
        "label": f"{primary.get('name', 'Component')} video",
        "icon": "video",
        "url": safe_url(primary.get("video_url"), primary.get("manual_url"), primary.get("url")),
    }

    return slots


def _summarize_resources(resource_slots: Dict[str, Dict[str, Any]]) -> str:
    """Build a short message describing what was mapped to the keypad."""
    if not resource_slots:
        return ""
    parts: List[str] = []
    for slot, cfg in resource_slots.items():
        label = cfg.get("label", slot)
        parts.append(f"{slot}: {label}")
    return "I've put resources on your keypad — " + "; ".join(parts) + "."


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
        # pretend to analyse scene with a VLM/LLM
        result = analyse_scene_with_vlm()
        state["mode"] = "scanned"
        state["components"] = result["components"]
        state["resource_slots"] = result["resource_slots"]

        buttons = _build_buttons_from_state(state["resource_slots"])

        summary = _build_summary_from_components(state["components"])

        return {
            "status": "ok",
            "mode": state["mode"],
            "message": summary,
            "buttons": buttons,
        }

    elif action.action == "talk":
        # Always stop any ongoing TTS when talk button is pressed
        stop_speech()
        
        if not state["talk_recording_active"]:
            buttons: List[Dict[str, Any]] = []
            if not state["components"] or not state["resource_slots"]:
                # Populate resource slots on first listen so keypad can react.
                result = analyse_scene_with_vlm()
                state["components"] = result["components"]
                state["resource_slots"] = result["resource_slots"]
                buttons = _build_buttons_from_state(state["resource_slots"])

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
            response = {
                "status": "ok",
                "mode": state["mode"],
                "message": (
                    "Jarvis is listening. Ask what you want to do with the "
                    "motherboard or RAM."
                ),
                "recording": recording_status(),
            }

            if buttons:
                response["buttons"] = buttons

            return response

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

        # Ensure resources are populated even if VLM missed them earlier.
        if not state["resource_slots"]:
            try:
                result = analyse_scene_with_vlm()
                state["components"] = result["components"]
                state["resource_slots"] = result["resource_slots"]
            except Exception as exc:  # noqa: BLE001
                print(f"[VLM] Failed to populate resources on stop: {exc}", file=sys.stderr)

        buttons = _build_buttons_from_state(state["resource_slots"])
        resource_note = _summarize_resources(state["resource_slots"])

        response_payload = {
            "status": processing.get("status", "ok"),
            "mode": state["mode"],
            "message": "Jarvis stopped listening." if not resource_note else resource_note,
            "recording": {"recording": False, "path": str(path)},
        }
        if buttons:
            response_payload["buttons"] = buttons
        response_payload.update(processing)
        return response_payload

    elif action.action == "stop":
        # Stop any ongoing TTS and recording, return idle state.
        stop_speech()
        if state["talk_recording_active"]:
            try:
                path = talk_recorder.stop()
                processing = _process_recording(Path(path))
                state["last_recording"] = str(path)
                state["last_transcript"] = processing.get("transcript")
                state["last_response"] = processing.get("assistant_text")
            except Exception as exc:  # noqa: BLE001
                processing = {"status": "error", "error": f"Failed to stop recording: {exc}"}
            finally:
                state["talk_recording_active"] = False
                state["current_recording"] = None
                state["mode"] = "idle"

            if not state["resource_slots"]:
                try:
                    result = analyse_scene_with_vlm()
                    state["components"] = result["components"]
                    state["resource_slots"] = result["resource_slots"]
                except Exception as exc:  # noqa: BLE001
                    print(f"[VLM] Failed to populate resources on stop action: {exc}", file=sys.stderr)

            buttons = _build_buttons_from_state(state["resource_slots"])
            resource_note = _summarize_resources(state["resource_slots"])

            response_payload = {
                "status": processing.get("status", "ok"),
                "mode": state["mode"],
                "message": "Jarvis stopped." if not resource_note else resource_note,
                "recording": {"recording": False, "path": state.get("last_recording")},
            }
            if buttons:
                response_payload["buttons"] = buttons
            response_payload.update(processing)
            return response_payload

        state["mode"] = "idle"
        return {"status": "ok", "mode": state["mode"], "message": "Jarvis stopped."}

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
        # dial rotation - your UI can use this later to move selection
        return {
            "status": "ok",
            "mode": state["mode"],
            "note": f"scroll tick={action.value}",
        }

    # Fallback
    return {"status": "ok", "mode": state["mode"]}
