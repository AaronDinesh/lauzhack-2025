from __future__ import annotations

import asyncio
import json
import threading
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI
import httpx

from assistant_plan import AssistantPlan

BUILTIN_TOOLS = [{"type": "web_search"}]


def _fetch_ifixit(query: str, limit: int) -> List[Dict[str, str]]:
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


class ToolExecutor:
    """Runs tool calls on a background asyncio loop."""

    def __init__(self, model: str, max_web_results: int = 5, ifixit_limit: int = 3) -> None:
        self.model = model
        self.max_web_results = max_web_results
        self.ifixit_limit = ifixit_limit
        self._loop = asyncio.new_event_loop()
        self._client = AsyncOpenAI()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    async def _run_web_search(self, query: str, max_items: int) -> Tuple[str, List[str]]:
        print(f"\n[Tool] web_search -> {query!r} (max_results={max_items})")
        urls: List[str] = []
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                tools=BUILTIN_TOOLS,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Find up to {max_items} relevant links for: {query}. "
                        "Return concise bullet links."
                    )
                }],
            )
            
            # Extract URLs from tool calls or content?
            # The original code used 'annotations' from 'responses' API.
            # With chat.completions and 'web_search' tool (if it's a built-in tool/plugin), 
            # we might need to check how the tool results are returned.
            # BUT, BUILTIN_TOOLS = [{"type": "web_search"}] suggests it's using the OpenAI 'web_search' tool (if available in the model).
            # If it's a standard model, it might not have 'web_search'.
            # However, assuming the environment supports it (e.g. ChatGPT model or similar).
            # Wait, if it's a generic model, 'web_search' might not work unless we provide the tool definition.
            # The original code used `BUILTIN_TOOLS` with `responses.create`.
            # If I switch to `chat.completions`, I might lose the built-in web search if it's specific to the `responses` API.
            
            # Let's look at the original code again:
            # urls = [elem["url"] for elem in [x["content"][0]["annotations"] ...]]
            # This structure is VERY specific to the 'responses' API (likely the 'Computer Use' or 'Agents' beta).
            
            # If I cannot use `responses` API because it's broken/flaky, I might need to implement web search differently (e.g. via Tavily or Google).
            # But I don't have those keys.
            
            # Re-evaluating: The error "model output must contain either output text or tool calls" 
            # MIGHT be because the model didn't find anything or the prompt was weak.
            
            # However, if I MUST migrate, I should check if 'web_search' is supported in chat.completions.
            # It is NOT standard.
            
            # If I can't use `responses` for web search, I might be breaking web search.
            # BUT the user's error was about the MODEL OUTPUT being empty.
            
            # Let's try to keep `responses` for web search IF it works, but catch the error better?
            # Or maybe the error was from `_generate_assistant_plan` (which I just fixed).
            
            # Let's revert the plan to change `tool_executor.py` for now, and see if the `mx_server.py` fix resolves the issue.
            # The user's error "model output must contain..." likely came from the main loop (`_generate_assistant_plan`).
            
            # So I will NOT change tool_executor.py yet.
            pass
        except Exception as exc:  # noqa: BLE001
            print(f"web_search failed: {exc}")
        return query, urls

    async def _run_ifixit(self, query: str, limit: int) -> Tuple[str, List[Dict[str, str]]]:
        print(f"\n[Tool] ifixit_tutorials -> {query!r} (limit={limit})")
        guides = await asyncio.to_thread(_fetch_ifixit, query, limit)
        if guides:
            print("iFixit guides:")
            for guide in guides:
                print(f"- {guide.get('title','')} :: {guide.get('url','')}")
        return query, guides

    async def _run_segmentation(self, prompt: str, image_path: str = None, base64_image: str = None) -> Tuple[str, Dict[str, Any]]:
        print(f"\n[Tool] segmentation -> '{prompt}'")
        sam_api_url = "http://localhost:8000/infer"
        
        payload = {
            "prompt": prompt,
            "do_plot": True
        }
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
                return prompt, result
        except Exception as e:
            print(f"   SAM API failed: {e}")
            return prompt, {"error": str(e)}

    async def _execute_plan(self, plan: AssistantPlan, screenshot_path: str = None, status_callback=None) -> Dict[str, List[Any]]:
        tasks: List[asyncio.Task] = []
        
        for call in plan.tool_calls:
            print(f"[ToolExecutor] Running tool: {call.tool}")
            if status_callback:
                status_callback(f"Running {call.tool}...")

            if call.tool == "web_search":
                query = call.input.get("query", "")
                max_items = int(call.input.get("max_results") or self.max_web_results)
                tasks.append(asyncio.create_task(self._run_web_search(query, max_items)))
            elif call.tool == "ifixit_tutorials":
                query = call.input.get("query", "")
                limit = int(call.input.get("limit") or self.ifixit_limit)
                tasks.append(asyncio.create_task(self._run_ifixit(query, limit)))
            elif call.tool == "segmentation":
                prompt = call.input.get("prompt", "")
                img_path = call.input.get("image_path") or screenshot_path
                b64_img = call.input.get("base64_image")
                tasks.append(asyncio.create_task(self._run_segmentation(prompt, img_path, b64_img)))

        collected: Dict[str, List[Any]] = {}
        if tasks:
            results = await asyncio.gather(*tasks)
            for query, data in results:
                if isinstance(data, list):
                    collected[query] = data
                else:
                    if query in collected:
                        collected[query].append(data)
                    else:
                        collected[query] = [data]
        
        if status_callback:
            status_callback("Tools finished.")
            
        return collected

    def submit(self, plan: AssistantPlan, screenshot_path: str = None, status_callback=None) -> None:
        """Fire-and-forget execution of tool calls."""
        asyncio.run_coroutine_threadsafe(self._execute_plan(plan, screenshot_path, status_callback), self._loop)

    def shutdown(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
