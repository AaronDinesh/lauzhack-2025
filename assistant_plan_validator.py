from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from openai import AsyncOpenAI

from assistant_plan import (
    AssistantPlan,
    build_system_prompt,
    encode_image,
    parse_assistant_plan_response,
)

BUILTIN_TOOLS = [{"type": "web_search"}]


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
        help="Max links to return when executing the web_search tool.",
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


async def _execute_tool_calls_async(
    plan: AssistantPlan, max_results: int, model: str
) -> Dict[str, List[str]]:
    client = AsyncOpenAI()

    async def run_search(query: str, max_items: int) -> Tuple[str, List[str]]:
        print(f"\n[Tool] web_search -> {query!r} (max_results={max_items})")
        try:
            response = await client.responses.create(
                model=model,
                tools=BUILTIN_TOOLS,
                reasoning={"effort": "low"},
                input=(
                    f"Find up to {max_items} relevant links for: {query}. "
                    "Return concise bullet links. Where possible find pdfs and files online."
                ),
            )

            response_dict = response.to_dict()
            urls = [
                elem["url"]
                for elem in [
                    x["content"][0]["annotations"]
                    for x in response_dict["output"]
                    if x["id"].startswith("msg")
                ][0]
            ]
            print(urls)
        except Exception as exc:  # noqa: BLE001
            print(f"web_search failed: {exc}")
            urls = []

        return query, urls

    tasks: List[asyncio.Task[Tuple[str, List[str]]]] = []
    for call in plan.tool_calls:
        if call.tool != "web_search":
            continue
        query = call.input.get("query", "")
        max_items = int(call.input.get("max_results") or max_results)
        tasks.append(asyncio.create_task(run_search(query, max_items)))

    collected: Dict[str, List[str]] = {}
    if tasks:
        results = await asyncio.gather(*tasks)
        for query, urls in results:
            collected[query] = urls

    return collected


async def amain() -> None:
    load_dotenv()
    args = _build_parser().parse_args()

    client = AsyncOpenAI()
    system_prompt = build_system_prompt()
    user_content = _build_user_content(args.prompt, args.screenshot)

    response = await client.responses.parse(
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
        reasoning={
            "effort": "minimal",
        },
    )

    plan = parse_assistant_plan_response(response)
    print("\nAssistant plan:")
    print(plan.model_dump_json(indent=2))

    if args.execute_tools and plan.tool_calls:
        urls_by_query = await _execute_tool_calls_async(plan, args.max_results, args.model)
        if urls_by_query:
            print("\nCollected URLs by query:")
            for query, urls in urls_by_query.items():
                print(f"- {query}:")
                for url in urls:
                    print(f"  {url}")
    elif args.execute_tools:
        print("\nNo tool calls requested by the assistant.")


if __name__ == "__main__":
    asyncio.run(amain())
