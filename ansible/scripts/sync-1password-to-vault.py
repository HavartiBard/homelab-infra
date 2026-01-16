#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Source of truth is 1Password. Playbooks read env -> vault only.
# This helper writes vault variables from Ansible-tagged 1Password items.
# Default behavior: write to the group vault (unraid/agh) with backup + prompt.
# Use --print-only to emit a snippet instead. Colors are ANSI when stdout is a tty.

ItemMap = List[Tuple[str, str, str]]  # (vault_key, op_item, op_field)

MAPPINGS: Dict[str, ItemMap] = {
    "unraid": [
        ("orbi_username_vault", "Orbi Login", "username"),
        ("orbi_password_vault", "Orbi Login", "password"),
        ("notion_token_vault", "Notion MCP Integration", "credential"),
        ("op_service_account_token_vault", "OP_SERVICE_ACCOUNT_TOKEN", "credential"),
        ("portainer_token_vault", "Portainer API Token", "credential"),
        ("proxmox_mcp_host_vault", "Proxmox MCP Token", "host"),
        ("proxmox_mcp_port_vault", "Proxmox MCP Token", "port"),
        ("proxmox_mcp_user_vault", "Proxmox MCP Token", "username"),
        ("proxmox_mcp_token_name_vault", "Proxmox MCP Token", "token_name"),
        ("proxmox_mcp_token_value_vault", "Proxmox MCP Token", "credential"),
        ("proxmox_mcp_allow_elevated_vault", "Proxmox MCP Token", "allow_elevated"),
        ("unraid_api_key_vault", "Unraid GraphQL - Wedge", "credential"),
        ("adguard_admin_user_vault", "AdGuard Admin", "username"),
        ("adguard_admin_password_vault", "AdGuard Admin", "password"),
        ("cloudflare_dns_token_vault", "Cloudflare DNS Token", "credential"),
        ("technitium_api_token_vault", "DNS Automation Credential", "credential"),
    ],
    "agh": [
        ("adguard_admin_user_vault", "AdGuard Admin", "username"),
        ("adguard_admin_password_vault", "AdGuard Admin", "password"),
    ],
}

MAPPINGS["all"] = sorted({entry for group in MAPPINGS.values() for entry in group}, key=lambda x: x[0])

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VAULT_PATH: Dict[str, Optional[Path]] = {
    "unraid": REPO_ROOT / "group_vars" / "unraid" / "vault.yml",
    "agh": REPO_ROOT / "group_vars" / "agh" / "vault.yml",
    "all": None,
}


def color(text: str, code: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def require_cmd(name: str) -> None:
    if shutil.which(name) is None:
        sys.stderr.write(f"Missing required command: {name}\n")
        sys.exit(1)


def require_op_session() -> None:
    try:
        run(["op", "whoami"])
    except subprocess.CalledProcessError as exc:
        sys.stderr.write("1Password CLI is not signed in. Run `eval $(op signin <account>)` and retry.\n")
        if exc.stderr:
            sys.stderr.write(f"{exc.stderr}\n")
        sys.exit(exc.returncode or 1)


def run(cmd: List[str]) -> str:
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def list_tagged_items() -> set:
    try:
        out = run(["op", "item", "list", "--tags", "Ansible", "--format", "json"])
        data = json.loads(out)
        return {item["title"] for item in data}
    except Exception as exc:
        sys.stderr.write(f"Warning: unable to list tagged items ({exc}); proceeding without tag filter\n")
        return set()


def get_field(item: str, field: str) -> str:
    return run(["op", "item", "get", item, "--fields", field, "--reveal"])


def build_snippet(group: str) -> str:
    tagged = list_tagged_items()
    if group not in MAPPINGS:
        sys.stderr.write(f"Unknown group '{group}'. Use unraid|agh|all.\n")
        sys.exit(1)

    lines = [f"# Vault snippet generated from 1Password (group={group})"]
    for key, item, field in MAPPINGS[group]:
        if tagged and item not in tagged:
            sys.stderr.write(f"# {key}: skipped; item '{item}' not tagged Ansible\n")
            continue
        try:
            val = get_field(item, field).replace('"', r'\"')
            lines.append(f'{key}: "{val}"')
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"# {key}: failed to fetch {item}.{field}: {exc}\n")
    return "\n".join(lines) + "\n"


def parse_existing_keys(decrypted: str) -> set:
    keys = set()
    for line in decrypted.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        keys.add(line.split(":", 1)[0])
    return keys


def snippet_keys(snippet: str) -> List[str]:
    keys = []
    for line in snippet.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        keys.append(line.split(":", 1)[0])
    return keys


def line_key(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        return None
    return stripped.split(":", 1)[0]


def merge_snippet(existing: str, snippet: str) -> str:
    # Replace keys found in snippet; drop duplicate keys in the existing content; append only new keys at the end.
    snippet_lines = [ln for ln in snippet.splitlines() if ln.strip()]
    snippet_order: List[str] = []
    snippet_map: Dict[str, str] = {}
    for ln in snippet_lines:
        k = line_key(ln)
        if k:
            if k not in snippet_order:
                snippet_order.append(k)
            snippet_map[k] = ln

    seen: set = set()
    merged_lines: List[str] = []
    for ln in existing.splitlines():
        k = line_key(ln)
        if k:
            if k in seen:
                continue  # drop duplicate occurrences in existing
            seen.add(k)
            if k in snippet_map:
                merged_lines.append(snippet_map.pop(k))
                continue
        merged_lines.append(ln)

    # Append any keys from snippet not present in existing.
    if snippet_map:
        if merged_lines and merged_lines[-1].strip():
            merged_lines.append("")
        for k in snippet_order:
            if k in snippet_map:
                merged_lines.append(snippet_map[k])

    return "\n".join(merged_lines).rstrip() + "\n"


def backup_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def prune_backups(vault_path: Path, keep: int = 3) -> None:
    pattern = vault_path.with_suffix(vault_path.suffix + ".bak.*").name
    backups = sorted(
        vault_path.parent.glob(pattern),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except Exception:
            pass


def apply_to_vault(
    snippet: str, vault_path: Path, password_file: Path, assume_yes: bool, encrypt_vault_id: Optional[str]
) -> bool:
    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)
    tmp_decrypted = Path(tmp_path)
    try:
        vault_exists = vault_path.exists()
        decrypted = ""

        if vault_exists:
            try:
                decrypted = run(
                    ["ansible-vault", "view", "--vault-password-file", str(password_file), str(vault_path)]
                )
            except subprocess.CalledProcessError as exc:
                sys.stderr.write(f"Failed to decrypt {vault_path}: {exc}\n")
                return False

            backup = vault_path.with_suffix(
                vault_path.suffix + f".bak.{backup_timestamp()}"
            )
            shutil.copy2(vault_path, backup)
            sys.stderr.write(f"{color('🗂️  backup created:', '33')} {backup}\n")
            prune_backups(vault_path)
        else:
            vault_path.parent.mkdir(parents=True, exist_ok=True)
            if not assume_yes:
                resp = input(
                    f"Vault {vault_path} does not exist. Create it using password file {password_file}? [y/N]: "
                ).strip().lower()
                if resp not in ("y", "yes"):
                    sys.stderr.write("Aborted by user (vault creation declined).\n")
                    return False
            sys.stderr.write(f"{color('🆕 creating vault:', '33')} {vault_path}\n")

        existing_keys = parse_existing_keys(decrypted)
        new_keys = snippet_keys(snippet)

        sys.stderr.write(f"{color('🔐 target vault:', '36')} {vault_path}\n")
        sys.stderr.write(f"{color('➡️  keys to set/update:', '36')} ({len(new_keys)})\n")
        for k in new_keys:
            status = color("update", "34") if k in existing_keys else color("add", "32")
            sys.stderr.write(f"   • {k} [{status}]\n")

        if not assume_yes:
            resp = input("Proceed with vault update? [y/N]: ").strip().lower()
            if resp not in ("y", "yes"):
                sys.stderr.write("Aborted by user.\n")
                return

        merged = merge_snippet(decrypted, snippet)
        tmp_decrypted.write_text(merged)
        sys.stderr.write(f"{color('📝 writing updated content...', '36')}\n")
        try:
            encrypt_cmd = [
                "ansible-vault",
                "encrypt",
                "--vault-password-file",
                str(password_file),
                "--output",
                str(vault_path),
            ]
            if encrypt_vault_id:
                encrypt_cmd.extend(["--encrypt-vault-id", encrypt_vault_id])
            encrypt_cmd.append(str(tmp_decrypted))
            run(
                encrypt_cmd
            )
        except subprocess.CalledProcessError as exc:
            sys.stderr.write("Failed to encrypt and write vault file.\n")
            if exc.stdout:
                sys.stderr.write(f"stdout:\n{exc.stdout}\n")
            if exc.stderr:
                sys.stderr.write(f"stderr:\n{exc.stderr}\n")
            return False
        sys.stderr.write(f"{color('✅ updated vault file:', '32')} {vault_path}\n")
        return True
    finally:
        tmp_decrypted.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Sync 1Password items (tagged Ansible) into Ansible vault vars.")
    parser.add_argument("--group", default="all", help="unraid|agh|all (default: all)")
    parser.add_argument("--vault", help="Path to ansible-vault file to update; if omitted, uses group default (if any)")
    parser.add_argument("--print-only", action="store_true", help="Print snippet to stdout instead of writing a vault")
    parser.add_argument("--yes", action="store_true", help="Apply without interactive confirmation")
    parser.add_argument(
        "--encrypt-vault-id",
        default=os.environ.get("ANSIBLE_VAULT_ENCRYPT_ID", "default"),
        help="Vault ID to encrypt with (passed to ansible-vault --encrypt-vault-id). Default: default; set to empty to omit.",
    )
    parser.add_argument(
        "--vault-password-file",
        default=os.environ.get("ANSIBLE_VAULT_PASSWORD_FILE"),
        help="Vault password file path (required when using --vault)",
    )
    args = parser.parse_args()

    require_cmd("op")
    require_cmd("ansible-vault")
    require_op_session()

    encrypt_vault_id = args.encrypt_vault_id if args.encrypt_vault_id else None

    if args.group == "all" and args.vault:
        sys.stderr.write("Cannot use --group all with a single --vault path; run per group or omit --vault.\n")
        sys.exit(1)

    if args.group == "all":
        groups = sorted([g for g in DEFAULT_VAULT_PATH.keys() if g != "all"])
        if not groups:
            sys.stderr.write("No group defaults configured; nothing to do.\n")
            sys.exit(1)
        overall_ok = True
        for g in groups:
            target = DEFAULT_VAULT_PATH.get(g)
            if target is None:
                sys.stderr.write(f"Skipping group {g}: no default vault path.\n")
                continue
            snippet = build_snippet(g)
            if args.print_only:
                sys.stdout.write(f"# --- snippet for group={g} ---\n")
                sys.stdout.write(snippet)
                continue
            if not args.vault_password_file:
                sys.stderr.write("Set --vault-password-file or ANSIBLE_VAULT_PASSWORD_FILE when using --vault.\n")
                sys.exit(1)
            ok = apply_to_vault(
                snippet,
                target,
                Path(args.vault_password_file),
                assume_yes=args.yes,
                encrypt_vault_id=encrypt_vault_id,
            )
            if not ok:
                overall_ok = False
        if not overall_ok:
            sys.exit(1)
        return

    snippet = build_snippet(args.group)

    if args.print_only:
        sys.stdout.write(snippet)
        return

    vault_target: Optional[Path] = Path(args.vault) if args.vault else DEFAULT_VAULT_PATH.get(args.group)
    if vault_target is None:
        sys.stderr.write("No default vault path for this group; pass --vault to specify a file.\n")
        sys.exit(1)

    if not args.vault_password_file:
        sys.stderr.write("Set --vault-password-file or ANSIBLE_VAULT_PASSWORD_FILE when using --vault.\n")
        sys.exit(1)

    ok = apply_to_vault(
        snippet,
        vault_target,
        Path(args.vault_password_file),
        assume_yes=args.yes,
        encrypt_vault_id=encrypt_vault_id,
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
