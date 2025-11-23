from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Literal, Optional, Sequence, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOL_GUIDANCE: Sequence[tuple[str, str]] = (
    (
        "segmentation",
        "For tutorials, generate a sequence of multiple tool calls to create a step-by-step guide. "
        "Break the process into logical steps. "
        "IMPORTANT: The 'prompt' field must be strictly a SINGULAR word (e.g., use 'ram stick' instead of 'ram sticks', or 'ram slot' instead of 'ram slots').",
    ),
    (
        "web_search",
        "Use OpenAI web_search when you need live web resources or troubleshooting links. Provide query and optional max_results (1-10) in your plan.",
    ),
    (
        "ifixit_tutorials",
        "Use iFixit tutorials when you need repair guides. Provide query and optional limit (1-10).",
    ),
)

# 2. SAM3 INPUT MODEL
class Sam3Input(BaseModel):
    prompt: str = Field(
        ..., 
        description="The text description of the element to segment (e.g., 'CPU socket', 'capacitor')."
    )
    image_path: Optional[str] = Field(
        None, 
        description="The absolute file path to the image on the server."
    )
    base64_image: Optional[str] = Field(
        None, 
        description="Base64 encoded image string (use this if the image is not saved to a file path)."
    )
    synonyms: Optional[List[str]] = Field(
        None, 
        description="Optional list of alternate names (e.g., ['processor socket', 'LGA1700']) to help with detection."
    )

class WebSearchInput(BaseModel):
    query: str = Field(..., description="Natural-language search query.")
    max_results: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of links to return.",
    )

class IFixitInput(BaseModel):
    query: str = Field(..., description="Search query for iFixit guides.")
    limit: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum number of tutorials to return.",
    )

# 3. UPDATED UNIFIED TOOL INPUT
# This must contain ALL fields from ALL tools (Union workaround)
class ToolInput(BaseModel):
    """Unified schema to stay within OpenAI json_schema limits (no unions)."""

    # --- SAM 3 Fields ---
    prompt: Optional[str] = Field(
        None,
        description="SAM3 prompt (description of object).",
    )
    image_path: Optional[str] = Field(
        None,
        description="SAM3 image file path.",
    )
    base64_image: Optional[str] = Field(
        None,
        description="SAM3 base64 encoded image.",
    )
    synonyms: Optional[List[str]] = Field(
        None,
        description="SAM3 synonyms.",
    )

    # --- Search / iFixit Fields ---
    query: Optional[str] = Field(
        None,
        description="Search query string.",
    )
    max_results: Optional[int] = Field(
        None,
        description="Search result limit.",
    )
    limit: Optional[int] = Field(
        None,
        description="iFixit tutorials result limit.",
    )

    model_config = ConfigDict(extra="forbid")


class ToolCall(BaseModel):
    tool: Literal["segmentation", "web_search", "ifixit_tutorials"]
    rationale: str = Field(..., description="The rationale for calling the tool.")
    input: ToolInput = Field(..., description="Tool-specific arguments.") # Initially defined as ToolInput

    @model_validator(mode="after")
    def validate_input_payload(self) -> "ToolCall":
        """
        Validates the unified input against the specific tool schema
        and converts self.input into a dictionary for easier execution.
        """
        # Convert the unified ToolInput model to a dict, removing None values
        payload = self.input.model_dump(exclude_none=True)

        if self.tool == "segmentation":
            # Validates that 'prompt' exists and structure matches Sam3Input
            self.input = Sam3Input.model_validate(payload).model_dump()
        elif self.tool == "web_search":
            self.input = WebSearchInput.model_validate(payload).model_dump()
        elif self.tool == "ifixit_tutorials":
            self.input = IFixitInput.model_validate(payload).model_dump()
        
        # Note: self.input is now a dict, not a ToolInput object
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


def build_system_prompt() -> str:
    lines = [
        "You are Jarvis.",
        "Always mention tools to use (if any) in the voice response.",
        "Pick the right tools for the task and provide minimal arguments.",
        "",
        "Available tools:",
    ]
    for name, guidance in TOOL_GUIDANCE:
        lines.append(f"- {name}: {guidance}")
    return "\n".join(lines)


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def parse_assistant_plan_response(response: object) -> AssistantPlan:
    """Extract the parsed AssistantPlan regardless of streaming/array shapes."""
    parsed = getattr(response, "parsed", None)

    if parsed:
        if isinstance(parsed, list):
            parsed = parsed[0]
        if isinstance(parsed, AssistantPlan):
            return parsed

    for item in getattr(response, "output", []) or []:
        for chunk in getattr(item, "content", []) or []:
            candidate = getattr(chunk, "parsed", None)
            if isinstance(candidate, AssistantPlan):
                return candidate

    raise RuntimeError("No parsed AssistantPlan returned from responses.parse()")