from __future__ import annotations

import argparse
import asyncio
import json
import urllib.parse
import urllib.request
import base64
from pathlib import Path
from typing import Any, Dict, List, Tuple

# pip install python-dotenv httpx openai
from dotenv import load_dotenv
from openai import AsyncOpenAI
import httpx

# Ensure this matches your local file name where the Pydantic models are defined
from assistant_plan import (
    AssistantPlan,
    build_system_prompt,
    encode_image,
    parse_assistant_plan_response,
)

# Standard OpenAI tools (SAM is handled client-side via tool_calls)
BUILTIN_TOOLS = [{"type": "web_search"}]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate structured assistant plans and execute multi-step tutorials.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-nano", # Updated default to a model that handles complex planning well
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
        default=3,
        help="Max links to return when executing the web_search tool.",
    )
    parser.add_argument(
        "--ifixit-limit",
        type=int,
        default=3,
        help="Max tutorials to return when executing the ifixit_tutorials tool.",
    )
    return parser


def _build_user_content(prompt: str, screenshot: Path | None) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    if screenshot:
        if not screenshot.is_file():
            raise FileNotFoundError(f"Screenshot not found: {screenshot}")
        
        # We append the path to the prompt text so the LLM knows what to put in 'image_path'
        content[0]["text"] += f"\n\n(Context: The image is located at: {screenshot.resolve()})"
        
        image_b64 = encode_image(screenshot)
        content.append({
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{image_b64}",
        })
    return content


async def _execute_tool_calls_async(
    plan: AssistantPlan, 
    max_results: int, 
    ifixit_limit: int, 
    model: str,
    screenshot_path: Path | None = None # Added to support implicit image passing
) -> Dict[str, List[Any]]:
    
    client = AsyncOpenAI()

    # --- 1. EXISTING: Web Search Tool ---
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
            try:
                urls = [
                    elem["url"]
                    for elem in [
                        x["content"][0]["annotations"]
                        for x in response_dict["output"]
                        if x["id"].startswith("msg")
                    ][0]
                ]
            except (KeyError, IndexError, TypeError):
                urls = []
            
            print(f"   Found {len(urls)} links.")
        except Exception as exc: 
            print(f"   web_search failed: {exc}")
            urls = []

        return query, urls

    # --- 2. EXISTING: iFixit Tool ---
    def fetch_ifixit(query: str, limit: int) -> List[Dict[str, str]]:
        base_url = "https://www.ifixit.com/api/2.0/suggest/"
        encoded_query = urllib.parse.quote(query)
        params = urllib.parse.urlencode({"doctypes": "guide", "limit": limit + 2})
        request_url = f"{base_url}{encoded_query}?{params}"

        try:
            with urllib.request.urlopen(request_url, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        guides: List[Dict[str, str]] = []
        for item in payload.get("results", []):
            if item.get("dataType") != "guide":
                continue
            guides.append(
                {
                    "title": item.get("title", "Unknown Guide"),
                    "url": item.get("url", ""),
                    "difficulty": item.get("difficulty", "Unknown"),
                    "image": (item.get("image") or {}).get("standard", ""),
                    "summary": item.get("summary", "No summary available"),
                }
            )
            if len(guides) >= limit:
                break
        return guides

    async def run_ifixit(query: str, limit: int) -> Tuple[str, List[Dict[str, str]]]:
        print(f"\n[Tool] ifixit_tutorials -> {query!r} (limit={limit})")
        urls = await asyncio.to_thread(fetch_ifixit, query, limit)
        if urls:
            print(f"   Found {len(urls)} guides.")
        return query, urls

    # --- 3. NEW: SAM 3 API Tool (Handles Multiple Steps) ---
    async def sam_request(prompt: str, image_path: str = None, base64_image: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        Sends a request to the local SAM 3 API.
        """
        sam_api_url = "http://localhost:8000/infer" 
        
        print(f"\n[Tool] segmentation -> '{prompt}'")

        payload = {
            "prompt": prompt,
            "do_plot": True
        }

        # Logic to ensure we have an image source
        if image_path:
            payload["image_path"] = image_path
        elif base64_image:
            payload["base64_image"] = base64_image
        else:
             print("   Error: No image provided for segmentation.")
             return prompt, {"error": "No image provided"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                response = await http_client.post(sam_api_url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                print(f"   SAM 3 Success: {result.get('num_objects', 0)} objects found.")
                print(f"   Overlay saved at: {result.get('overlay_path')}")
                return prompt, result
                
        except Exception as e:
            print(f"   SAM API failed: {e}")
            return prompt, {"error": str(e)}

    # --- Task Dispatcher ---
    tasks: List[asyncio.Task[Tuple[str, Any]]] = []
    
    # We iterate over the list of calls. For a tutorial, this list will contain
    # multiple segmentation calls (Step 1, Step 2, Step 3).
    for call in plan.tool_calls:
        
        if call.instruction:
            print(f"\n[Instruction] {call.instruction}")

        if call.tool == "web_search":
            # Note: We cast input to dict because our updated ToolCall validator converts it
            input_data = call.input if isinstance(call.input, dict) else call.input.model_dump()
            query = input_data.get("query", "")
            max_items = int(input_data.get("max_results") or max_results)
            tasks.append(asyncio.create_task(run_search(query, max_items)))
            
        elif call.tool == "ifixit_tutorials":
            input_data = call.input if isinstance(call.input, dict) else call.input.model_dump()
            query = input_data.get("query", "")
            limit = int(input_data.get("limit") or ifixit_limit)
            tasks.append(asyncio.create_task(run_ifixit(query, limit)))

        # NEW: Handle the Segmentation tool
        elif call.tool == "segmentation":
            input_data = call.input if isinstance(call.input, dict) else call.input.model_dump()
            
            prompt_text = input_data.get("prompt", "")
            img_path = input_data.get("image_path")
            b64_img = input_data.get("base64_image")

            # FALLBACK: If LLM didn't provide path, use the CLI arg
            if not img_path and not b64_img and screenshot_path:
                img_path = str(screenshot_path.resolve())

            tasks.append(asyncio.create_task(sam_request(prompt_text, img_path, b64_img)))

    collected: Dict[str, List[Any]] = {}
    if tasks:
        # Run all steps in parallel (or sequential if you prefer, but parallel is faster)
        results = await asyncio.gather(*tasks)
        for query, data in results:
            # We wrap single dict results in a list to maintain consistency with other tools
            if isinstance(data, list):
                collected[query] = data
            else:
                # Initialize list if key doesn't exist (handles multiple steps with same prompt name? 
                # Better to use a unique key or append, but for this schema:
                if query in collected:
                    collected[query].append(data)
                else:
                    collected[query] = [data]

    return collected


async def amain() -> None:
    load_dotenv()
    args = _build_parser().parse_args()

    client = AsyncOpenAI()
    system_prompt = build_system_prompt()
    user_content = _build_user_content(args.prompt, args.screenshot)

    print("Sending request to LLM...")
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
            "effort": "low", # Use 'low' or 'medium' for faster responses
        },
    )

    plan = parse_assistant_plan_response(response)
    print("\nAssistant plan:")
    print(plan.model_dump_json(indent=2))
    
    # Print the "Voice" response immediately
    print(f"\n[Jarvis]: {plan.voice}")

    if args.execute_tools and plan.tool_calls:
        print("\nExecuting Tool Calls...")
        urls_by_query = await _execute_tool_calls_async(
            plan, 
            args.max_results, 
            args.ifixit_limit, 
            args.model,
            screenshot_path=args.screenshot # Pass the path down!
        )
        
        if urls_by_query:
            print("\n--- Execution Results ---")
            for query, items in urls_by_query.items():
                print(f"Query/Prompt: {query}")
                for item in items:
                    if isinstance(item, dict):
                        # Handle SAM output
                        if 'overlay_path' in item:
                            print(f"  [Segmentation] Image saved: {item.get('overlay_path')}")
                            print(f"  [Segmentation] Confidence: {item.get('scores', [])}")
                        # Handle Web/iFixit output
                        elif 'url' in item:
                            print(f"  [Link] {item.get('title','')} :: {item.get('url','')}")
                        else:
                            print(f"  {item}")
                    else:
                        print(f"  {item}")
                        
    elif args.execute_tools:
        print("\nNo tool calls requested by the assistant.")


if __name__ == "__main__":
    asyncio.run(amain())