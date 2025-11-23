from __future__ import annotations

import asyncio
import json
import threading
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI

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
            response = await self._client.responses.create(
                model=self.model,
                tools=BUILTIN_TOOLS,
                reasoning={"effort": "low"},
                input=(
                    f"Find up to {max_items} relevant links for: {query}. "
                    "Return concise bullet links."
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
                if isinstance(elem, dict) and "url" in elem
            ]
            if urls:
                print("web_search URLs:")
                for url in urls:
                    print(f"- {url}")
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

    async def _execute_plan(self, plan: AssistantPlan) -> Dict[str, List[Any]]:
        tasks: List[asyncio.Task] = []
        for call in plan.tool_calls:
            if call.tool == "web_search":
                query = call.input.get("query", "")
                max_items = int(call.input.get("max_results") or self.max_web_results)
                tasks.append(asyncio.create_task(self._run_web_search(query, max_items)))
            elif call.tool == "ifixit_tutorials":
                query = call.input.get("query", "")
                limit = int(call.input.get("limit") or self.ifixit_limit)
                tasks.append(asyncio.create_task(self._run_ifixit(query, limit)))

        collected: Dict[str, List[Any]] = {}
        if tasks:
            results = await asyncio.gather(*tasks)
            for query, urls in results:
                collected[query] = urls
        return collected

    def submit(self, plan: AssistantPlan) -> None:
        """Fire-and-forget execution of tool calls."""
        asyncio.run_coroutine_threadsafe(self._execute_plan(plan), self._loop)

    def shutdown(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
