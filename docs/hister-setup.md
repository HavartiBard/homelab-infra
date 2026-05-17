# Hister Search Engine Setup

## Overview

Hister is your **personal search engine** that indexes your browsing history and local files. It's designed to be the primary search tool with fallback to external engines.

## Architecture

```
User Search
    │
    ├─→ Hister (personal history) ── if not found ──→ !! ──→ External Engine
    │
    └─→ AI Tools (MCP) ── direct Hister MCP connection
```

## Current Configuration

| Service | URL | Port | Purpose |
|---------|-----|------|---------|
| Hister Web UI | https://search.klsll.com | 4433 | Main interface |
| Hister MCP | http://192.168.20.14:4433/mcp | 4433 | AI agent integration |
| SearXNG (fallback) | http://192.168.20.14:6979/search | 6979 | External search fallback |

## Search Workflow

### For Manual Searches (Browser)

1. **Open Hister** via:
   - Browser bookmark: `https://search.klsll.com`
   - Global hotkey (e.g., `Win+S` → opens Hister in new tab)

2. **Search your history** - queries index automatically

3. **If not found**:
   - Type `!!` at start/end of query + Enter
   - OR press `Alt+O` to open current query in external search

### For AI Tools

**Claude Code / Codex / other MCP clients** connect directly to Hister:

```json
{
  "mcpServers": {
    "hister": {
      "url": "http://192.168.20.14:4433/mcp",
      "headers": {
        "Authorization": "Bearer <your-access-token>",
        "Origin": "hister://"
      }
    }
  }
}
```

**Open WebUI** uses SearXNG for broad web search (not Hister MCP).

## Configuration Tasks

### 1. Set Hister as Browser Default Search

**Chrome:**
1. Settings → Search engine → Manage search engines
2. Add new search engine: `https://search.klsll.com/?q=%s`
3. Set as default

**Firefox:**
1. Settings → Search → Search Shortcuts
2. Add "Hister" with URL: `https://search.klsll.com/?q=%s`
3. Set as default

### 2. Configure External Search Fallback

Open Hister web UI → Settings → External Search → Set to:
```
http://192.168.20.14:6979/search?q=<query>&format=json
```

This makes `!!` fallback use SearXNG (which aggregates Bing, startpage, Wikipedia).

### 3. Install Browser Extension (Optional but Recommended)

Install the Hister browser extension for automatic indexing:

- [Chrome Web Store](https://chromewebstore.google.com/detail/hister/cciilamhchpmbdnniabclekddabkifhb)
- [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/hister/)

The extension auto-indexes pages you visit.

## Quick Commands

### Test Hister MCP
```bash
curl -s -X POST http://192.168.20.14:4433/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: hister://" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search","arguments":{"query":"python","limit":3}}}' | jq .
```

### Test SearXNG (fallback)
```bash
curl -s "http://192.168.20.14:6979/search?q=test&format=json" | jq .
```

### Add Skip Rule (prevent indexing noise)
```bash
# View current rules
docker exec hister cat /hister/data/rules.json

# Add skip rule via web UI: Settings → Rules → Skip rules
# Example: `domain:twitter.com` or `domain:facebook.com`
```

### Pre-index Documentation
```bash
# Index a specific URL recursively
docker exec hister hister index --recursive https://pkg.go.dev/some/library

# Dry run to see what would be indexed
docker exec hister hister index --dry https://pkg.go.dev/some/library
```

## Troubleshooting

### Hister not responding
```bash
docker ps | grep hister
docker logs hister -f
curl -v http://192.168.20.14:4433/
```

### MCP endpoint not working
```bash
curl -s -X POST http://192.168.20.14:4433/mcp \
  -H "Content-Type: application/json" \
  -H "Origin: hister://" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq .
```

### Fallback not working
1. Check Hister Settings → External Search is configured
2. Verify SearXNG is running: `curl http://192.168.20.14:6979/`
3. Test fallback manually: search `!! python` in Hister

## Comparison: Hister vs SearXNG

| Aspect | Hister | SearXNG |
|--------|--------|---------|
| Data source | Your browsing history + indexed pages | The entire web |
| Privacy | Local only | Local, but queries external engines |
| Speed | Instant (local DB) | Depends on external engines |
| AI integration | Native MCP support | Not MCP-native |
| Best for | Re-finding what you've seen | Discovering new content |

## Summary

**Use Hister for:**
- Re-finding pages you've visited
- Searching indexed documentation
- AI tool context (MCP integration)

**Use SearXNG for:**
- General web discovery
- News/current events
- Content outside your history

**The `!!` mechanism bridges them** - start with Hister, fall back to SearXNG automatically.
