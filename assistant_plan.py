from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


TOOL_GUIDANCE: Sequence[tuple[str, str]] = (
    (
        "segmentation",
        "Use SAM3 when you must segment an element in an image. Provide target_element and 1-5 synonyms.",
    ),
    (
        "web_search",
        "Use OpenAI web_search when you need live web resources or troubleshooting links. Provide query and optional max_results (1-10) in your plan.",
    ),
)


class Sam3Input(BaseModel):
    target_element: str = Field(..., description="The element to segment in the image.")
    synonyms: List[str] = Field(
        ..., description="Alternate words for the target element."
    )


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Natural-language search query.")
    max_results: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of links to return.",
    )


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
        description="Search query string.",
    )
    max_results: Optional[int] = Field(
        None,
        description="Search result limit.",
    )

    model_config = ConfigDict(extra="forbid")


class ToolCall(BaseModel):
    tool: Literal["segmentation", "web_search"]
    rationale: str = Field(..., description="The rationale for calling the tool.")
    input: ToolInput = Field(..., description="Tool-specific arguments.")

    @model_validator(mode="after")
    def validate_input_payload(self) -> "ToolCall":
        """Keep the JSON schema simple while still validating locally."""
        payload = self.input.model_dump(exclude_none=True)
        if self.tool == "segmentation":
            self.input = Sam3Input.model_validate(payload).model_dump()
        elif self.tool == "web_search":
            self.input = WebSearchInput.model_validate(payload).model_dump()
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
