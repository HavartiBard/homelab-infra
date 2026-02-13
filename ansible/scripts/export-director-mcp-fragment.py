#!/usr/bin/env python3
"""Export MCP endpoints from homelab-infra Ansible defaults into a Director fragment.

The output fragment is intended to be consumed by director-playbooks as an input
fragment under `director/config/fragments/`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROLE_MAP = [
    {
        "role": "unraid-mcp",
        "name": "unraid-mcp",
        "port_var": "unraid_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "homelab-mcp",
        "name": "homelab-mcp",
        "port_var": "homelab_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "onepassword-mcp",
        "name": "onepassword-mcp",
        "port_var": "onepassword_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "portainer-mcp",
        "name": "portainer-mcp",
        "port_var": "portainer_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "proxmox-mcp",
        "name": "proxmox-mcp",
        "port_var": "proxmox_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "gitea-mcp",
        "name": "gitea-mcp",
        "port_var": "gitea_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "notion-mcp",
        "name": "notion-mcp-public",
        "port_var": "notion_mcp_port",
        "path": "/mcp",
    },
    {
        "role": "mcp-proxy",
        "name": "mcp-proxy",
        "port_var": "mcp_proxy_port",
        "path": "/servers/soullayer/sse",
    },
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected YAML mapping in {path}")
    return data


def resolve_unraid_host(inventory_path: Path) -> str:
    inventory = load_yaml(inventory_path)
    hosts = (
        inventory.get("all", {})
        .get("children", {})
        .get("unraid", {})
        .get("hosts", {})
    )
    if not isinstance(hosts, dict) or not hosts:
        raise RuntimeError(
            f"Could not find unraid hosts in inventory: {inventory_path}"
        )

    first_host_data = next(iter(hosts.values()))
    if not isinstance(first_host_data, dict):
        raise RuntimeError("Unexpected unraid host entry type in inventory")

    ansible_host = first_host_data.get("ansible_host")
    if not isinstance(ansible_host, str) or not ansible_host.strip():
        raise RuntimeError("Missing ansible_host for first unraid inventory entry")

    return ansible_host.strip()


def build_servers(roles_dir: Path, unraid_host: str) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = []
    for item in ROLE_MAP:
        defaults_path = roles_dir / item["role"] / "defaults" / "main.yml"
        if not defaults_path.exists():
            continue

        defaults = load_yaml(defaults_path)
        raw_port = defaults.get(item["port_var"])

        if raw_port is None:
            continue

        port = str(raw_port).strip()
        if not port:
            continue

        path = item["path"]
        url = f"http://{unraid_host}:{port}{path}"

        servers.append(
            {
                "name": item["name"],
                "type": "http",
                "url": url,
            }
        )

    return servers


def write_fragment(output_path: Path, playbook: str, servers: list[dict[str, Any]]) -> None:
    doc = {
        "playbooks": {
            playbook: {
                "servers": servers,
            }
        }
    }

    header = (
        "# GENERATED FILE - do not edit directly\n"
        "# Source: homelab-infra/ansible roles defaults\n"
        f"# Generated at: {datetime.now(timezone.utc).isoformat()}\n"
    )
    yaml_body = yaml.safe_dump(doc, sort_keys=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(header)
        fh.write(yaml_body)


def default_output_path(repo_root: Path) -> Path:
    return (
        repo_root.parent
        / "director-playbooks"
        / "director"
        / "config"
        / "fragments"
        / "15-homelab-mcps.generated.yaml"
    )


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]

    parser = argparse.ArgumentParser(
        description=(
            "Generate a Director fragment that registers MCP servers derived "
            "from homelab-infra role defaults."
        )
    )
    parser.add_argument(
        "--inventory",
        default=str(repo_root / "ansible" / "inventory" / "hosts.yml"),
        help="Path to ansible inventory hosts.yml",
    )
    parser.add_argument(
        "--roles-dir",
        default=str(repo_root / "ansible" / "roles"),
        help="Path to ansible roles directory",
    )
    parser.add_argument(
        "--output",
        default=str(default_output_path(repo_root)),
        help="Output fragment path",
    )
    parser.add_argument(
        "--playbook",
        default="dev-core",
        help="Target Director playbook name for exported servers",
    )
    parser.add_argument(
        "--unraid-host",
        default=None,
        help="Override unraid host/IP instead of resolving from inventory",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    inventory_path = Path(args.inventory).resolve()
    roles_dir = Path(args.roles_dir).resolve()
    output_path = Path(args.output).resolve()

    unraid_host = args.unraid_host.strip() if args.unraid_host else resolve_unraid_host(
        inventory_path
    )
    servers = build_servers(roles_dir, unraid_host)

    write_fragment(output_path, args.playbook, servers)

    print(f"Exported {len(servers)} MCP server(s) to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
