"""Smoke-test harness for the observability stack.

The stack is managed by Ansible under ``ansible/files/observability`` and
published via the deployment playbooks in ``ansible/playbooks/observability``.
This harness keeps the checks lightweight and supports three run modes:

- ``static``: validate the checked-in configuration
- ``live``: probe externally reachable services
- ``full``: run both static and live checks, including internal-only checks
  via ``--docker-exec``
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
OBSERVABILITY_DIR = REPO_ROOT / "ansible" / "files" / "observability"
COMPOSE_FILE = OBSERVABILITY_DIR / "compose.yml"

STATIC_REQUIRED_FILES = [
    "compose.yml",
    "prometheus/prometheus.yml",
    "prometheus/rules/alerts.yml",
    "loki/config.yml",
    "grafana/provisioning/datasources/datasources.yml",
    "grafana/provisioning/dashboards/dashboards.yml",
    "syslog-ng/syslog-ng.conf",
    "../../roles/observability/templates/alertmanager.yml.j2",
]

STATIC_CONTENT_CHECKS = {
    "compose.yml": ["loki", "prometheus", "grafana", "syslog-ng", "alertmanager"],
    "prometheus/rules/alerts.yml": ["HostDown", "DiskSpaceLow", "ContainerRestartLoop"],
    "grafana/provisioning/datasources/datasources.yml": ["Loki", "Prometheus"],
    "../../roles/observability/templates/alertmanager.yml.j2": ["vault_alertmanager_slack_webhook_url"],
}

LIVE_CHECKS = [
    ("grafana health", "http://127.0.0.1:3030/api/health", "http"),
    ("syslog-ng tcp listener", ("127.0.0.1", 5514), "tcp"),
]

INTERNAL_LIVE_CHECKS = [
    ("loki readiness", "http://loki:3100/ready", "ready"),
    ("prometheus health", "http://prometheus:9090/-/healthy", "healthy"),
    ("alertmanager health", "http://alertmanager:9093/-/healthy", "ok"),
]


@dataclass(slots=True)
class CheckResult:
    """Result for a single smoke-test check."""

    name: str
    passed: bool
    message: str

    def format(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.message}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_command(command: Sequence[str], *, cwd: Path | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _result(name: str, passed: bool, message: str) -> CheckResult:
    return CheckResult(name=name, passed=passed, message=message)


def _check_files_exist() -> list[CheckResult]:
    results: list[CheckResult] = []
    for relative in STATIC_REQUIRED_FILES:
        path = OBSERVABILITY_DIR / relative
        if path.exists():
            results.append(_result(relative, True, "present"))
        else:
            results.append(_result(relative, False, f"missing: {path}"))
    return results


def _check_expected_content() -> list[CheckResult]:
    results: list[CheckResult] = []
    for relative, snippets in STATIC_CONTENT_CHECKS.items():
        path = OBSERVABILITY_DIR / relative
        if not path.exists():
            results.append(_result(relative, False, "file missing, skipping content validation"))
            continue
        content = _read_text(path)
        missing = [snippet for snippet in snippets if snippet not in content]
        if missing:
            results.append(
                _result(relative, False, f"missing expected text: {', '.join(missing)}")
            )
        else:
            results.append(_result(relative, True, "expected content present"))
    return results


def _check_compose_config() -> CheckResult:
    # Docker Compose reads .env files from the current directory
    # Write a temporary .env file and run config from that directory
    env_content = "\n".join(
        [
            "OBSERVABILITY_APPDATA=/tmp/observability-smoke",
            "GRAFANA_ADMIN_PASSWORD=smoke-test-password",
            "",
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text(env_content, encoding="utf-8")
        proc = _run_command(
            ["docker-compose", "-f", str(COMPOSE_FILE), "config"],
            cwd=tmpdir,
            timeout=60.0,
        )

    if proc.returncode == 0:
        return _result("docker compose config", True, "configuration renders successfully")
    stderr = (proc.stderr or proc.stdout or "compose config failed").strip()
    return _result("docker compose config", False, stderr)


def run_static_checks() -> list[CheckResult]:
    """Validate the checked-in observability configuration."""

    results = _check_files_exist()
    results.extend(_check_expected_content())
    results.append(_check_compose_config())
    return results


def _check_http_json(url: str, *, timeout: float) -> CheckResult:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _result(url, False, f"request failed: {exc}")

    if status != 200:
        return _result(url, False, f"unexpected status: {status}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _result(url, False, "response was not valid JSON")

    if payload.get("database") != "ok":
        return _result(url, False, f"unexpected health payload: {payload}")
    return _result(url, True, "Grafana reports database=ok")


def _check_tcp_listener(host: str, port: int, *, timeout: float) -> CheckResult:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return _result(f"tcp://{host}:{port}", False, f"connection failed: {exc}")
    return _result(f"tcp://{host}:{port}", True, "connection accepted")


def _check_docker_http(container: str, url: str, expected_substring: str, *, timeout: float) -> CheckResult:
    proc = _run_command(["docker", "exec", container, "wget", "-qO-", url], timeout=timeout)
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "docker exec failed").strip()
        return _result(f"docker exec {container} {url}", False, stderr)

    body = (proc.stdout or "").strip()
    if expected_substring.lower() not in body.lower():
        return _result(
            f"docker exec {container} {url}",
            False,
            f"missing '{expected_substring}' in response: {body}",
        )
    return _result(f"docker exec {container} {url}", True, f"response contained '{expected_substring}'")


def run_live_checks(*, timeout: float, docker_exec_container: str | None = None, require_internal: bool = False, grafana_url: str = LIVE_CHECKS[0][1], syslog_host: str = LIVE_CHECKS[1][1][0], syslog_port: int = LIVE_CHECKS[1][1][1]) -> list[CheckResult]:
    """Probe the live observability services."""

    results = [
        _check_http_json(grafana_url, timeout=timeout),
        _check_tcp_listener(syslog_host, syslog_port, timeout=timeout),
    ]

    if docker_exec_container:
        results.extend(
            _check_docker_http(docker_exec_container, url, expected, timeout=timeout)
            for _, url, expected in INTERNAL_LIVE_CHECKS
        )
    elif require_internal:
        results.append(
            _result(
                "internal services",
                False,
                "full mode requires --docker-exec so Loki, Prometheus, and Alertmanager can be checked",
            )
        )

    return results


def run_checks(
    mode: str,
    *,
    timeout: float = 10.0,
    docker_exec_container: str | None = None,
    grafana_url: str = LIVE_CHECKS[0][1],
    syslog_host: str = LIVE_CHECKS[1][1][0],
    syslog_port: int = LIVE_CHECKS[1][1][1],
) -> list[CheckResult]:
    """Run the requested smoke-test mode."""

    results: list[CheckResult] = []
    if mode in {"static", "full"}:
        results.extend(run_static_checks())
    if mode in {"live", "full"}:
        results.extend(
            run_live_checks(
                timeout=timeout,
                docker_exec_container=docker_exec_container,
                require_internal=mode == "full",
                grafana_url=grafana_url,
                syslog_host=syslog_host,
                syslog_port=syslog_port,
            )
        )
    return results


def _print_results(results: Iterable[CheckResult]) -> None:
    for result in results:
        print(result.format())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run observability smoke tests")
    parser.add_argument("mode", choices=("static", "live", "full"), help="Which checks to run")
    parser.add_argument(
        "--docker-exec",
        nargs="?",
        const="grafana",
        metavar="CONTAINER",
        help="Run internal-only checks via docker exec into CONTAINER (defaults to grafana)",
    )
    parser.add_argument(
        "--grafana-url",
        default=LIVE_CHECKS[0][1],
        help="Grafana health endpoint to probe in live mode",
    )
    parser.add_argument("--syslog-host", default=LIVE_CHECKS[1][1][0], help="Host for the syslog-ng TCP check")
    parser.add_argument(
        "--syslog-port",
        type=int,
        default=LIVE_CHECKS[1][1][1],
        help="Port for the syslog-ng TCP check",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-check timeout in seconds")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    results = run_checks(
        args.mode,
        timeout=args.timeout,
        docker_exec_container=args.docker_exec,
        grafana_url=args.grafana_url,
        syslog_host=args.syslog_host,
        syslog_port=args.syslog_port,
    )
    _print_results(results)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
