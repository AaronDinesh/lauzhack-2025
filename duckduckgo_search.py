from __future__ import annotations

import html
import re
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

# Matches <a class="...result__url...">...</a> capturing href and inner text.
_RESULT_URL_RE = re.compile(
    r'<a[^>]*class="[^"]*result__url[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _normalize_href(raw_href: str) -> str | None:
    """Return a usable external URL or None."""
    if not raw_href:
        return None

    # Handle protocol-relative links (//example.com/path)
    if raw_href.startswith("//"):
        raw_href = f"https:{raw_href}"

    parsed = urlparse(raw_href)

    # DuckDuckGo wraps outbound links like https://duckduckgo.com/l/?uddg=<url>
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg", [])
        if uddg:
            decoded = html.unescape(uddg[0])
            if decoded.startswith("//"):
                decoded = f"https:{decoded}"
            if decoded.startswith("http://") or decoded.startswith("https://"):
                return decoded
        return None

    if parsed.scheme in ("http", "https"):
        return raw_href
    return None


def _scrape_duckduckgo_html(
    query: str, *, max_results: int, timeout: float
) -> List[Dict[str, str]]:
    params = urlencode({"q": query, "ia": "web"})
    url = f"https://duckduckgo.com/html/?{params}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0"
        },
    )

    with urlopen(request, timeout=timeout) as response:
        html_text = response.read().decode("utf-8", errors="ignore")

    results: List[Dict[str, str]] = []
    seen: set[str] = set()
    print(html_text)
    for match in _RESULT_URL_RE.finditer(html_text):
        raw_href, raw_inner = match.group(1), match.group(2)
        target_url = _normalize_href(raw_href)
        if not target_url:
            continue
        if target_url in seen:
            continue
        seen.add(target_url)
        title_text = html.unescape(raw_inner)
        title_text = re.sub(r"\s+", " ", title_text).strip()
        results.append({"title": title_text or target_url, "url": target_url})
        if len(results) >= max_results:
            break

    return results


def search_duckduckgo(
    query: str, *, max_results: int = 5, timeout: float = 8.0
) -> List[Dict[str, str]]:
    """
    Scrape DuckDuckGo HTML results page and return the first N external URLs via regex.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    max_results = max(1, min(max_results, 10))

    return _scrape_duckduckgo_html(query, max_results=max_results, timeout=timeout)
