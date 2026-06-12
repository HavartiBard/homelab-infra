"""Minimal hister REST client for the archive_page MCP tool."""

import os

HISTER_URL = os.environ.get("HISTER_URL", "http://192.168.20.14:4433")


def build_payload(url, title, text, label=None):
    """Build the JSON body for hister POST /api/add."""
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError(f"url must start with http:// or https://, got: {url!r}")
    if not text or not text.strip():
        raise ValueError("text must be non-empty — pass the curated page content")
    payload = {"url": url, "title": title or url, "text": text}
    if label:
        payload["label"] = label
    return payload


def archive_to_hister(url, title, text, label=None):
    """Index a document in hister, handling the cookie+CSRF handshake.

    hister requires a session cookie plus the X-Csrf-Token value returned
    as a response header by GET /api/config on every mutating request.
    """
    import httpx  # imported here so tests need no pip deps

    payload = build_payload(url, title, text, label)
    with httpx.Client(base_url=HISTER_URL, timeout=30) as client:
        config_resp = client.get("/api/config")
        config_resp.raise_for_status()
        csrf_token = config_resp.headers["x-csrf-token"]
        resp = client.post("/api/add", json=payload, headers={"X-Csrf-Token": csrf_token})
        resp.raise_for_status()
        return resp.text.strip()
