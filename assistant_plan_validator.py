from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from assistant_plan import (
    AssistantPlan,
    build_system_prompt,
    encode_image,
    parse_assistant_plan_response,
)
from duckduckgo_search import search_duckduckgo


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate structured assistant plans and optionally execute tool calls.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-nano",
        help="OpenAI Responses model to use.",
    )
    parser.add_argument(
        "--prompt",
        default="Describe what you see on the desk. Identify the numbers in the keyboard.",
        help="User prompt to send along with the image.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Path to an image to include in the request.",
    )
    parser.add_argument(
        "--execute-tools",
        action="store_true",
        help="Run supported tools after parsing the assistant plan.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Max links to return when executing the search_web tool.",
    )
    return parser


def _build_user_content(prompt: str, screenshot: Path | None) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    if screenshot:
        if not screenshot.is_file():
            raise FileNotFoundError(f"Screenshot not found: {screenshot}")
        image_b64 = encode_image(screenshot)
        content.append({
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{image_b64}",
        })
    return content


def _execute_tool_calls(plan: AssistantPlan, max_results: int) -> None:
    for call in plan.tool_calls:
        if call.tool != "search_web":
            continue

        query = call.input.get("query", "")
        max_items = int(call.input.get("max_results") or max_results)
        print(f"\n[Tool] search_web -> {query!r} (max_results={max_items})")
        try:
            results = search_duckduckgo(query, max_results=max_items)
        except Exception as exc:  # noqa: BLE001
            print(f"search_web failed: {exc}")
            continue

        for idx, item in enumerate(results, start=1):
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            print(f"{idx}. {title}\n   {url}")


def main() -> None:
    load_dotenv()
    args = _build_parser().parse_args()

    client = OpenAI()
    system_prompt = build_system_prompt()
    user_content = _build_user_content(args.prompt, args.screenshot)

    response = client.responses.parse(
        model=args.model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        text_format=AssistantPlan,
        reasoning={"effort": "minimal"},
    )

    plan = parse_assistant_plan_response(response)
    print("\nAssistant plan:")
    print(plan.model_dump_json(indent=2))

    if args.execute_tools and plan.tool_calls:
        _execute_tool_calls(plan, args.max_results)
    elif args.execute_tools:
        print("\nNo tool calls requested by the assistant.")


if __name__ == "__main__":
    main()
