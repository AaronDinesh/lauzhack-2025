import json
import os
import sys
import threading
import asyncio
from pathlib import Path
from time import perf_counter, time as current_time
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
import zmq

from audio.recorder import ContinuousRecorder
from audio.speech_to_text import transcribe_file_sync
from audio.text_to_speech import speak_text, stop_speech
from audio.notifications import play_tool_complete_sound
from camera.helpers import (
    FrameCache,
    capture_with_context,
    capture_frame,
    save_frame_to_logs,
    build_image_content,
)
from assistant_plan import (
    AssistantPlan,
    build_system_prompt,
    parse_assistant_plan_response,
    encode_image,
)
from tool_executor import ToolExecutor

load_dotenv()

app = FastAPI(title="Jarvis Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConsoleAction(BaseModel):
    action: str
    value: Optional[int] = None

class ResourceItem(BaseModel):
    label: str
    url: str
    icon: Optional[str] = None

class ResourceUpdate(BaseModel):
    resources: List[ResourceItem]

state: Dict[str, Any] = {
    "mode": "idle",
    "components": [],      # filled after scan
    "resource_slots": {},  # maps "resource_1" -> {"label", "icon", "url", ...}
    "current_recording": None,
    "last_recording": None,
    "talk_recording_active": False,
    "last_transcript": None,
    "last_response": None,
    "workspace_split": 70,  # percentage allocated to camera
    "last_plan": None,
    "tools_active": False,
    "active_tools": [],
    "last_tool_status": None,
}

MODEL_NAME = os.getenv("JARVIS_RESPONSES_MODEL", "gpt-5-nano")
VOICE_PRESET = os.getenv("OPENAI_TTS_VOICE", "alloy")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
REASONING_EFFORT = os.getenv("JARVIS_REASONING_EFFORT", "minimal")
DEFAULT_SYSTEM_PROMPT = build_system_prompt()
SYSTEM_PROMPT = os.getenv("JARVIS_SYSTEM_PROMPT", "").strip() or DEFAULT_SYSTEM_PROMPT
EXIT_PHRASES = {
    phrase.strip().lower()
    for phrase in os.getenv("JARVIS_EXIT_PHRASES", "quit,exit,goodbye").split(",")
    if phrase.strip()
}
CAMERA_INDEX = int(os.getenv("JARVIS_CAMERA_INDEX", "0"))
FRAME_ZMQ_BIND = os.getenv("FRAME_ZMQ_BIND", "tcp://127.0.0.1:5557")

# Disable local camera frame cache when UI snapshots are arriving via ZeroMQ.
USE_FRAME_CACHE = os.getenv("USE_FRAME_CACHE", "0").lower() in {"1", "true", "yes"}

client = OpenAI()

conversation: List[Dict[str, Any]] = []
if SYSTEM_PROMPT:
    conversation.append(
        {
            "role": "system",
            "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
        }
    )

frame_cache: FrameCache | None = None  # initialized at startup if enabled
tool_executor: ToolExecutor | None = None
_tts_thread_lock = threading.Lock()
_active_tts_thread: threading.Thread | None = None
_ui_frame: Dict[str, Any] = {"data": None, "ts": 0.0}
_zmq_context: Optional[zmq.Context] = None
_zmq_thread: Optional[threading.Thread] = None
_zmq_stop = threading.Event()
_sse_subscribers: List[asyncio.Queue] = []


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


def _request_assistant_plan(conversation_history: List[Dict[str, Any]]) -> AssistantPlan:
    request_kwargs: Dict[str, Any] = {
        "model": MODEL_NAME,
        "input": conversation_history,
        "text_format": AssistantPlan,
    }
    if REASONING_EFFORT:
        request_kwargs["reasoning"] = {"effort": REASONING_EFFORT}
    response = client.responses.parse(**request_kwargs)
    return parse_assistant_plan_response(response)


def _play_tool_sound_async() -> None:
    def _worker() -> None:
        try:
            play_tool_complete_sound()
        except Exception as exc:  # noqa: BLE001
            print(f"[Audio] Tool completion sound failed: {exc}", file=sys.stderr)

    threading.Thread(target=_worker, name="tool-done-chime", daemon=True).start()


def _reset_tool_state(clear_status: bool = False) -> None:
    state["tools_active"] = False
    state["active_tools"] = []
    if clear_status:
        state["last_tool_status"] = None


def _handle_tool_status_update(message: str) -> None:
    print(f"[Tools] {message}")
    state["last_tool_status"] = message
    lowered = message.lower()
    if lowered.startswith("running"):
        state["tools_active"] = True
    elif "finished" in lowered or "failed" in lowered:
        state["tools_active"] = False
        if state["active_tools"]:
            _play_tool_sound_async()
        state["active_tools"] = []


def _dispatch_tool_plan(
    plan: AssistantPlan,
    screenshot_path: Path,
    screenshot_base64: str | None,
) -> None:
    if not plan.tool_calls:
        _reset_tool_state(clear_status=True)
        return

    state["tools_active"] = True
    state["active_tools"] = [call.tool for call in plan.tool_calls]
    queued_summary = f"Running {len(plan.tool_calls)} tool(s)..."
    state["last_tool_status"] = queued_summary
    print(f"[Tools] {queued_summary}")

    if tool_executor is None:
        print("[Tools] ToolExecutor not initialized; skipping tool execution", file=sys.stderr)
        state["tools_active"] = False
        state["last_tool_status"] = "Tool executor unavailable"
        state["active_tools"] = []
        return

    tool_executor.submit(
        plan,
        str(screenshot_path),
        screenshot_base64,
        status_callback=_handle_tool_status_update,
    )


def _get_ui_frame_bytes(max_age: float = 1.5) -> Optional[bytes]:
    data = _ui_frame.get("data")
    ts = _ui_frame.get("ts", 0.0)
    if data is None:
        return None
    if (current_time() - ts) > max_age:
        return None
    return data


def _frame_listener() -> None:
    global _zmq_context
    if not FRAME_ZMQ_BIND:
        return
    context = zmq.Context.instance()
    _zmq_context = context
    socket = context.socket(zmq.PULL)
    socket.linger = 0
    try:
        socket.bind(FRAME_ZMQ_BIND)
    except Exception as exc:  # noqa: BLE001
        print(f"[ZMQ] Failed to bind to {FRAME_ZMQ_BIND}: {exc}", file=sys.stderr)
        socket.close()
        return

    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    print(f"[ZMQ] Listening for frames on {FRAME_ZMQ_BIND}")

    try:
        while not _zmq_stop.is_set():
            events = dict(poller.poll(500))
            if socket in events and events[socket] == zmq.POLLIN:
                try:
                    parts = socket.recv_multipart(flags=zmq.NOBLOCK)
                except zmq.Again:
                    continue
                if not parts:
                    continue
                payload = parts[-1]
                _ui_frame["data"] = payload
                _ui_frame["ts"] = current_time()
    finally:
        poller.unregister(socket)
        socket.close()


def broadcast_event(event: Dict[str, Any]) -> None:
    if not _sse_subscribers:
        return
    message = json.dumps(event)
    for queue in list(_sse_subscribers):
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass
        except Exception:
            try:
                _sse_subscribers.remove(queue)
            except ValueError:
                pass


def fetch_frame_with_context(user_text: str) -> tuple[list[dict], Path]:
    """
    Capture a frame supplied by the UI (via ZeroMQ) if available, otherwise fall back to
    the local camera. Returns OpenAI-ready content plus the saved screenshot path.
    """
    jpeg_bytes = _get_ui_frame_bytes()
    if jpeg_bytes is None:
        content, screenshot_path = capture_with_context(
            user_text,
            camera_index=CAMERA_INDEX,
            frame_cache=frame_cache if USE_FRAME_CACHE else None,
        )
        return content, screenshot_path

    saved_path = save_frame_to_logs(jpeg_bytes)
    content = build_image_content(user_text, jpeg_bytes)
    return content, saved_path


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

    screenshot_b64: Optional[str] = None
    try:
        content, screenshot_path = fetch_frame_with_context(transcript)
        step_start = _log_step_duration("fetch_frame_with_context", step_start)
        print(f"[Pipeline] Captured screenshot at {screenshot_path}")
        try:
            screenshot_b64 = encode_image(screenshot_path)
        except Exception as encode_exc:  # noqa: BLE001
            print(f"[Pipeline] Failed to encode screenshot: {encode_exc}", file=sys.stderr)
    except Exception as exc:
        return {
            "status": "error",
            "error": f"Camera capture failed: {exc}",
            "transcript": transcript,
        }

    conversation.append({"role": "user", "content": content})

    plan: AssistantPlan | None = None
    plan_error: Optional[str] = None
    assistant_text = ""

    try:
        plan = _request_assistant_plan(conversation)
        assistant_text = plan.voice.strip()
        step_start = _log_step_duration("responses.parse", step_start)
    except Exception as exc:
        plan_error = str(exc)
        print(f"[Planning] AssistantPlan parsing failed: {exc}", file=sys.stderr)
        try:
            assistant_text = _stream_assistant_text(conversation)
            step_start = _log_step_duration("responses.stream", step_start)
        except Exception as stream_exc:
            conversation.pop()  # remove the failed user turn
            return {
                "status": "error",
                "error": f"Assistant streaming failed: {stream_exc}",
                "transcript": transcript,
            }

    if not assistant_text:
        conversation.pop()
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

    plan_dict: Optional[Dict[str, Any]] = None
    if plan:
        plan_dict = plan.model_dump()
        state["last_plan"] = plan_dict
        _dispatch_tool_plan(plan, screenshot_path, screenshot_b64)
    else:
        state["last_plan"] = None

    result: Dict[str, Any] = {
        "status": "ok",
        "transcript": transcript,
        "assistant_text": assistant_text,
        "screenshot_path": screenshot_path,
        "plan": plan_dict,
        "tools_active": state["tools_active"],
        "active_tools": state["active_tools"],
        "last_tool_status": state["last_tool_status"],
    }
    if plan_dict and "tool_calls" in plan_dict:
        result["tool_calls"] = plan_dict["tool_calls"]
    if plan_error:
        result["plan_error"] = plan_error
    if tts_error:
        result["tts_error"] = tts_error
    return result


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


@app.on_event("startup")
def _startup() -> None:
    global frame_cache, _zmq_thread, tool_executor
    if USE_FRAME_CACHE:
        try:
            frame_cache = FrameCache(camera_index=CAMERA_INDEX, refresh_interval=0.2)
            frame_cache.start()
            frame_cache.wait_until_ready(timeout=3.0)
            print("[Startup] Frame cache initialized")
        except Exception as exc:
            print(f"Frame cache unavailable: {exc}", file=sys.stderr)
            if frame_cache:
                frame_cache.stop()
                frame_cache = None

    if FRAME_ZMQ_BIND:
        _zmq_stop.clear()
        _zmq_thread = threading.Thread(target=_frame_listener, name="ui-frame-listener", daemon=True)
        _zmq_thread.start()

    if tool_executor is None:
        tool_executor = ToolExecutor(model=MODEL_NAME)


@app.on_event("shutdown")
def _shutdown() -> None:
    global tool_executor
    if frame_cache:
        frame_cache.stop()
    _zmq_stop.set()
    if _zmq_thread:
        _zmq_thread.join(timeout=1.0)
    if _zmq_context:
        try:
            _zmq_context.term()
        except Exception:
            pass
    if tool_executor:
        tool_executor.shutdown()
        tool_executor = None


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

    if action.action == "talk":
        # Always stop any ongoing TTS when talk button is pressed
        stop_speech()
        
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
            response = {
                "status": "ok",
                "mode": state["mode"],
                "message": (
                    "Jarvis is listening. Ask what you want to do with the "
                    "motherboard or RAM."
                ),
                "recording": recording_status(),
            }

            return response

        try:
            path = talk_recorder.stop()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "error": f"Failed to stop talk recording: {exc}",
                "recording": recording_status(),
            }

        state["mode"] = "processing"
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

    elif action.action == "stop":
        # Stop any ongoing TTS and recording, return idle state.
        stop_speech()
        if state["talk_recording_active"]:
            try:
                path = talk_recorder.stop()
            except Exception as exc:  # noqa: BLE001
                return {
                    "status": "error",
                    "error": f"Failed to stop talk recording: {exc}",
                    "recording": recording_status(),
                }

            state["mode"] = "processing"
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
        response = {
            "status": "ok",
            "mode": state["mode"],
            "note": f"scroll tick={action.value}",
        }
        broadcast_event({"type": "scroll_component", "payload": {"value": action.value}})
        return response

    elif action.action == "resize_panel":
        delta = action.value or 0
        current = float(state.get("workspace_split", 70))
        new_value = int(min(max(current + delta * 1, 30), 85))
        state["workspace_split"] = new_value
        response = {
            "status": "ok",
            "mode": state["mode"],
            "workspace_split": new_value,
        }
        broadcast_event({"type": "setLayout", "payload": {"workspaceSplit": new_value}})
        return response

    # Fallback
    return {"status": "ok", "mode": state["mode"]}


@app.get("/status")
def get_status():
    """
    Lightweight endpoint the UI can poll for current state.
    """
    return {
        "mode": state.get("mode", "idle"),
        "talking": state.get("talk_recording_active", False),
        "listening": state.get("talk_recording_active", False),
        "last_transcript": state.get("last_transcript"),
        "last_response": state.get("last_response"),
        "workspace_split": state.get("workspace_split", 70),
        "last_plan": state.get("last_plan"),
        "tools_active": state.get("tools_active", False),
        "active_tools": state.get("active_tools", []),
        "last_tool_status": state.get("last_tool_status"),
    }


@app.get("/stream")
async def stream_events():
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(json.dumps({"type": "setLayout", "payload": {"workspaceSplit": state.get("workspace_split", 70)}}))
    _sse_subscribers.append(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/frame")
def get_frame():
    """
    Serve the latest camera frame as JPEG for the UI to display.
    """
    jpeg_bytes = _get_ui_frame_bytes(max_age=1.0)
    if jpeg_bytes is None and frame_cache:
        jpeg_bytes = frame_cache.get_latest_frame(max_age=0.5)

    if jpeg_bytes is None:
        try:
            jpeg_bytes = capture_frame(camera_index=CAMERA_INDEX)
        except Exception as exc:  # noqa: BLE001
            return Response(
                content=f"Failed to capture frame: {exc}",
                media_type="text/plain",
                status_code=500,
            )

    return Response(content=jpeg_bytes, media_type="image/jpeg")


@app.post("/resources/update")
def update_resources(update: ResourceUpdate):
    resources = update.resources
    if not resources:
        return {"status": "ok", "updated": 0}

    new_slots: Dict[str, Dict[str, str]] = {}
    for idx, item in enumerate(resources[:3], start=1):
        label = item.label.strip() or f"Resource {idx}"
        url = item.url.strip()
        if not url:
            continue
        new_slots[f"resource_{idx}"] = {
            "label": label[:60],
            "icon": (item.icon or "link").strip() or "link",
            "url": url,
        }

    if not new_slots:
        return {"status": "error", "error": "no valid resources"}

    state["resource_slots"] = new_slots
    broadcast_event({"type": "resources", "payload": new_slots})
    return {"status": "ok", "updated": len(new_slots)}
