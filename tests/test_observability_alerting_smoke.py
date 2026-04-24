from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from chiffon.observability import smoke


class DummyResponse:
    def __init__(self, payload: dict[str, object], status: int = 200):
        self._payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self) -> int:
        return self.status


@pytest.fixture()
def command_log(monkeypatch):
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(command, cwd=None, check=False, capture_output=False, text=False, timeout=None):
        calls.append((list(command), cwd))
        if command[:2] == ["docker", "compose"]:
            return subprocess.CompletedProcess(command, 0, stdout="config ok", stderr="")
        if command[:2] == ["docker", "exec"]:
            url = command[-1]
            payloads = {
                "http://loki:3100/ready": "ready",
                "http://prometheus:9090/-/healthy": "Prometheus is Healthy.",
                "http://alertmanager:9093/-/healthy": "OK",
            }
            return subprocess.CompletedProcess(command, 0, stdout=payloads[url], stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    return calls


def test_main_static_mode_validates_compose(command_log, monkeypatch):
    monkeypatch.setattr(
        smoke.urllib.request,
        "urlopen",
        lambda request, timeout=0: pytest.fail("static mode should not make HTTP requests"),
    )
    monkeypatch.setattr(
        smoke.socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail("static mode should not make TCP connections"),
    )

    exit_code = smoke.main(["static"])

    assert exit_code == 0
    assert any(cmd[:2] == ["docker", "compose"] for cmd, _ in command_log)


def test_main_live_mode_checks_public_services_without_docker_exec(monkeypatch):
    command_log: list[list[str]] = []

    def fake_run(command, cwd=None, check=False, capture_output=False, text=False, timeout=None):
        command_log.append(list(command))
        raise AssertionError("live mode without --docker-exec should not use docker exec")

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(smoke.urllib.request, "urlopen", lambda request, timeout=0: DummyResponse({"database": "ok"}))
    monkeypatch.setattr(smoke.socket, "create_connection", lambda *args, **kwargs: FakeSocket())

    exit_code = smoke.main(["live"])

    assert exit_code == 0
    assert command_log == []


def test_main_full_mode_with_docker_exec_checks_internal_services(monkeypatch, command_log):
    monkeypatch.setattr(smoke.urllib.request, "urlopen", lambda request, timeout=0: DummyResponse({"database": "ok"}))

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(smoke.socket, "create_connection", lambda *args, **kwargs: FakeSocket())

    exit_code = smoke.main(["full", "--docker-exec"])

    assert exit_code == 0
    assert any(cmd[:2] == ["docker", "compose"] for cmd, _ in command_log)
    assert any(cmd[:3] == ["docker", "exec", "grafana"] for cmd, _ in command_log)


def test_full_mode_requires_docker_exec(monkeypatch):
    monkeypatch.setattr(smoke.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="config ok", stderr=""))
    monkeypatch.setattr(smoke.urllib.request, "urlopen", lambda request, timeout=0: DummyResponse({"database": "ok"}))

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(smoke.socket, "create_connection", lambda *args, **kwargs: FakeSocket())

    exit_code = smoke.main(["full"])

    assert exit_code == 1


def test_parser_defaults_to_grafana_container():
    parser = smoke.build_parser()
    args = parser.parse_args(["full", "--docker-exec"])
    assert args.docker_exec == "grafana"


def test_package_exports():
    assert smoke.CheckResult(name="demo", passed=True, message="ok").format() == "[PASS] demo: ok"
