"""hister-archive-mcp — MCP server exposing hister's write path.

Part of the web research stack: agents discover with SearXNG, scrape with
Crawl4AI, then deliberately archive worthwhile pages into hister with this
tool. Archiving is opt-in curation — never bulk-archive raw search results.

hister's own native MCP is read-only (search/get_preview); this is
specifically the write-bridge, plus a cheap pre-check so agents don't
re-archive a URL that's already indexed.
"""

from mcp.server.fastmcp import FastMCP

import hister_client

mcp = FastMCP("hister-archive", host="0.0.0.0", port=3000)


@mcp.tool()
def archive_page(url: str, text: str, title: str = "", label: str = "") -> str:
    """Archive a web page into hister (the personal search index).

    Use this AFTER scraping a page (e.g. with Crawl4AI) and deciding it is
    worth keeping. Pass the page URL and the extracted plain-text content.
    Check is_archived(url) first to avoid re-archiving the same page.

    Args:
        url: The page URL (must be http/https).
        text: Extracted plain-text content of the page.
        title: Page title (defaults to the URL if omitted).
        label: Optional hister label for later filtering, e.g. "research".
    """
    result = hister_client.archive_to_hister(url, title or None, text, label or None)
    return f"Archived {url} in hister: {result}"


@mcp.tool()
def is_archived(url: str) -> str:
    """Check whether a URL is already archived in hister.

    Call this before archive_page to avoid creating duplicate entries.

    Args:
        url: The page URL to check.
    """
    doc = hister_client.get_document(url)
    if doc is None:
        return f"Not archived: {url}"
    title = doc.get("title") or url
    label = doc.get("label") or ""
    return f"Already archived: {url} (title={title!r}, label={label!r})"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
