from __future__ import annotations

from duckduckgo_search import search_duckduckgo


def main() -> None:
    query = "ASUS TUF Gaming GeForce RTX 3090 manual PDF site:asus.com"
    results = search_duckduckgo(query, max_results=5)
    print(f"Query: {query}")
    for idx, item in enumerate(results, start=1):
        print(f"{idx}. {item['title']}\n   {item['url']}")
    if not results:
        raise SystemExit("No results returned from DuckDuckGo scraper.")


if __name__ == "__main__":
    main()
