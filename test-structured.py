from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Literal, Optional

from dotenv import load_dotenv

from openai import OpenAI
from pydantic import BaseModel, Field, ConfigDict, model_validator

load_dotenv()


class Sam3Input(BaseModel):
    target_element: str = Field(..., description="The element to segment in the image.")
    synonyms: List[str] = Field(
        ..., description="Alternate words for the target element."
    )


class SearchOnlineInput(BaseModel):
    query: str = Field(..., description="The query to search the web for.")


class ToolInput(BaseModel):
    """Unified schema to stay within OpenAI json_schema limits (no unions)."""

    target_element: Optional[str] = Field(
        None,
        description="SAM3 target element description.",
    )
    synonyms: Optional[List[str]] = Field(
        None,
        description="SAM3 synonyms.",
    )
    query: Optional[str] = Field(
        None,
        description="SearchOnline query string.",
    )

    model_config = ConfigDict(extra="forbid")

class ToolCall(BaseModel):
    tool: Literal["segmentation", "search_online"]
    rationale: str = Field(..., description="The rationale for calling the tool.")
    input: ToolInput = Field(..., description="Tool-specific arguments.")

    @model_validator(mode="after")
    def validate_input_payload(self) -> "ToolCall":
        """Keep the JSON schema simple while still validating locally."""
        payload = self.input.model_dump(exclude_none=True)
        if self.tool == "segmentation":
            self.input = Sam3Input.model_validate(payload).model_dump()
        elif self.tool == "search_online":
            self.input = SearchOnlineInput.model_validate(payload).model_dump()
        return self

class AssistantPlan(BaseModel):
    voice: str = Field(
        ...,
        description="Exact sentence to speak to the user right now; must mention any tools to use if any.",
    )
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="Zero or more tool invocations to launch immediately. Decide which tool to use based on the task at hand.",
    )

def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def run_validation() -> None:
    client = OpenAI()
    screenshot = Path(
        "/Users/carloshurtado/Documents/lauzhack-2025/logs/screenshot-20251122-215712.jpg"
    )
    image_b64 = _encode_image(screenshot)

    response = client.responses.parse(
        model="gpt-5-nano",
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are Jarvis. Only call SAM3 when you need to segment a UI element in the "
                            "picture. Supply target_element + 1-5 synonyms. Call SearchOnline only when "
                            "you need fresh web info; provide query. Always "
                            "mention tools to use if any in the voice response."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Describe what you see on the desk. This is a segmentation task. Identify the numbers in my keyboard."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_b64}",
                    },
                ],
            },
        ],
        text_format=AssistantPlan,
        reasoning={"effort": "minimal"},
    )

    # responses.parse already validates the schema; pull the parsed object safely
    plan: AssistantPlan | None = None
    parsed = getattr(response, "parsed", None)
    if parsed:
        if isinstance(parsed, list):
            plan = parsed[0]
        else:
            plan = parsed

    if plan is None:
        for item in response.output or []:
            for chunk in item.content or []:
                candidate = getattr(chunk, "parsed", None)
                if candidate:
                    plan = candidate if isinstance(candidate, AssistantPlan) else None
                    break
            if plan:
                break

    if plan is None:
        raise RuntimeError("No parsed AssistantPlan returned from responses.parse()")

    print(plan.model_dump_json(indent=2))


if __name__ == "__main__":
    run_validation()