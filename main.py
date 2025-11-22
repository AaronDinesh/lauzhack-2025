from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

app = FastAPI(title="Jarvis Backend")

class ConsoleAction(BaseModel):
    device: str          
    control: str        
    event: str         
    action: str        
    value: Optional[int] = None 

state: Dict[str, Any] = {
    "mode": "idle",
    "components": [],      # filled after scan
    "resource_slots": {},  # maps "resource_1" -> {"label", "icon", "url", ...}
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
        state["mode"] = "talking"
        # STT + chat LLM pipeline plugs in here.
        return {
            "status": "ok",
            "mode": state["mode"],
            "message": (
                "Jarvis is listening. Ask what you want to do with the "
                "motherboard or RAM."
            ),
        }

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
