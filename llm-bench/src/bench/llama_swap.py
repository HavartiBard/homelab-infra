"""Minimal client for [llama-swap](https://github.com/mostlygeek/llama-swap).

llama-swap is an OpenAI-compatible proxy that hot-swaps llama-server processes
per requested model. This module provides:

- ``list_models()`` — discover which models the proxy is configured to serve
- ``pre_warm(model)`` — trigger a model load before a benchmark starts, so
  the first prompt's TTFT isn't inflated by 30-90s of model load time

We intentionally rely only on the OpenAI-compatible endpoints (`/v1/models`,
`/v1/chat/completions`) rather than llama-swap's admin API. Pre-warming via a
1-token chat request is equivalent to calling an explicit load endpoint and
works regardless of admin-API exposure / version.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx


log = logging.getLogger(__name__)


class LlamaSwapClient:
    """Thin OpenAI-compatible client targeted at llama-swap's behavior.

    Args:
        base_url: e.g. ``http://goudai.lab.klsll.com:8010/v1``. May or may not
            include a trailing slash. The ``/chat/completions`` path is
            appended for pre-warm requests; ``/models`` for listing.
        api_key: optional bearer token. Empty string disables auth header.
        timeout: per-request HTTP timeout in seconds. The pre-warm timeout
            should be generous (~120s) because the first request after a
            model swap blocks until the new model finishes loading.
    """

    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def list_models(self) -> list[str]:
        """Return the model IDs the proxy advertises via ``GET /v1/models``.

        Raises ``RuntimeError`` if the endpoint is unreachable. An empty list
        is a valid (though unusual) result — it indicates llama-swap is up
        but no models are configured.
        """
        url = f"{self.base_url}/models"
        try:
            resp = httpx.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"llama-swap list_models failed: {exc}") from exc

        data = resp.json()
        return [item.get("id", "") for item in data.get("data", []) if item.get("id")]

    def pre_warm(self, model: str) -> float:
        """Force ``model`` to be loaded by sending a 1-token chat request.

        Returns wall-clock seconds taken for the load+response — useful as a
        provenance field on the run record ("warm time was 47s, so this
        wasn't a cached state").

        Raises ``RuntimeError`` on transport failure or non-2xx response.
        Idempotent: if the model is already loaded, the request returns
        quickly without re-loading.
        """
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": "."}],
            "max_tokens": 1,
            # Skip thinking-mode if the model is reasoning-capable. We want
            # the fastest possible round-trip, not a chain-of-thought.
            "chat_template_kwargs": {"enable_thinking": False},
        }

        start = time.perf_counter()
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"llama-swap pre_warm({model!r}) failed: {exc}"
            ) from exc

        elapsed = time.perf_counter() - start
        log.info("Pre-warm %s completed in %.1fs", model, elapsed)
        return elapsed
