"""Tests for the LlamaSwapClient helper used by the runner pre-warm hook."""

from __future__ import annotations

import pytest

from bench.llama_swap import LlamaSwapClient


class TestListModels:
    def test_returns_model_ids(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={
                "data": [
                    {"id": "qwen/qwen3.6-27b-mtp"},
                    {"id": "qwen/qwen3-coder-next"},
                ]
            },
        )
        client = LlamaSwapClient("http://test/v1")
        assert client.list_models() == ["qwen/qwen3.6-27b-mtp", "qwen/qwen3-coder-next"]

    def test_strips_trailing_slash(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "m"}]},
        )
        client = LlamaSwapClient("http://test/v1/")
        assert client.list_models() == ["m"]

    def test_filters_entries_without_id(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "good"}, {"foo": "bar"}, {"id": ""}]},
        )
        client = LlamaSwapClient("http://test/v1")
        assert client.list_models() == ["good"]

    def test_empty_list_is_valid(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": []},
        )
        client = LlamaSwapClient("http://test/v1")
        assert client.list_models() == []

    def test_includes_bearer_token(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "m"}]},
            match_headers={"Authorization": "Bearer secret"},
        )
        client = LlamaSwapClient("http://test/v1", api_key="secret")
        client.list_models()
        assert httpx_mock.get_request().headers["Authorization"] == "Bearer secret"

    def test_omits_auth_header_when_no_key(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "m"}]},
        )
        client = LlamaSwapClient("http://test/v1")
        client.list_models()
        assert "Authorization" not in httpx_mock.get_request().headers

    def test_raises_runtime_error_on_http_failure(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            status_code=500,
        )
        client = LlamaSwapClient("http://test/v1")
        with pytest.raises(RuntimeError, match="list_models failed"):
            client.list_models()


class TestPreWarm:
    def test_sends_single_token_request(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/chat/completions",
            json={
                "choices": [{"message": {"role": "assistant", "content": "."}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        client = LlamaSwapClient("http://test/v1")
        elapsed = client.pre_warm("qwen/qwen3.6-27b-mtp")

        assert elapsed >= 0
        req = httpx_mock.get_request()
        import json
        body = json.loads(req.read())
        assert body["model"] == "qwen/qwen3.6-27b-mtp"
        assert body["max_tokens"] == 1
        # Crucial — we want zero thinking overhead on the pre-warm
        assert body["chat_template_kwargs"] == {"enable_thinking": False}

    def test_returns_positive_elapsed_seconds(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/chat/completions",
            json={"choices": [{"message": {"role": "assistant", "content": "."}}]},
        )
        client = LlamaSwapClient("http://test/v1")
        elapsed = client.pre_warm("m")
        assert isinstance(elapsed, float)
        assert elapsed >= 0

    def test_raises_runtime_error_on_http_failure(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/chat/completions",
            status_code=503,
        )
        client = LlamaSwapClient("http://test/v1")
        with pytest.raises(RuntimeError, match=r"pre_warm\('m'\) failed"):
            client.pre_warm("m")

    def test_strips_trailing_slash(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/chat/completions",
            json={"choices": [{"message": {"role": "assistant", "content": "."}}]},
        )
        client = LlamaSwapClient("http://test/v1/")
        client.pre_warm("m")
        # If the slash weren't stripped, the URL would be /v1//chat/completions
        # and httpx_mock wouldn't match the registered endpoint.
        assert httpx_mock.get_request() is not None
