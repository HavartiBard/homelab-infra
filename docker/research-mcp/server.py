"""research-mcp — MCP server exposing the hister archive tool.

Part of the web research stack: agents discover with SearXNG, scrape with
Crawl4AI, then deliberately archive worthwhile pages into hister with this
tool. Archiving is opt-in curation — never bulk-archive raw search results.
"""

from mcp.server.fastmcp import FastMCP

import hister_client

mcp = FastMCP("research-archive", host="0.0.0.0", port=3000)


@mcp.tool()
def archive_page(url: str, text: str, title: str = "", label: str = "") -> str:
    """Archive a web page into hister (the personal search index).

    Use this AFTER scraping a page (e.g. with Crawl4AI) and deciding it is
    worth keeping. Pass the page URL and the extracted plain-text content.

    Args:
        url: The page URL (must be http/https).
        text: Extracted plain-text content of the page.
        title: Page title (defaults to the URL if omitted).
        label: Optional hister label for later filtering, e.g. "research".
    """
    result = hister_client.archive_to_hister(url, title or None, text, label or None)
    return f"Archived {url} in hister: {result}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
