# VS Code Remote Tunnel

Bring this VM into VS Code via the official Remote Tunnel CLI. The tunnel runs as a systemd **user** service (no inbound ports) with a stable name of `dev-vm`.

## What this sets up
- Installs the upstream VS Code CLI into `~/.local/share/vscode-cli` and links `~/.local/bin/code`
- Stores tunnel state and credentials in `~/.vscode-tunnel` (keep this on the VM)
- User systemd unit: `~/.config/systemd/user/vscode-tunnel.service` → `ExecStart=~/.local/share/vscode-cli/bin/code tunnel --name dev-vm --accept-server-license-terms`
- Linger enabled (`loginctl enable-linger james`) so the user service starts at boot without an active login
- Outbound-only tunnel; no new inbound ports opened

## Install / refresh
From the repo root:

```bash
./scripts/setup_vscode_tunnel.sh
```

What it does:
- Ensures `code` CLI is available (downloads the VS Code CLI tarball if needed)
- Enables linger for the current user (sudo prompt) so the user service can run at boot
- Links `systemd/vscode-tunnel.service` into `~/.config/systemd/user/`, reloads, enables, and starts it
- Prints status/log commands and the browser URL

Re-run the script any time to pick up updates; it is idempotent.

## First-time sign-in (device code)
The tunnel needs a one-time device-code sign-in. Default provider is GitHub. Run this interactively under the `james` user:

```bash
VSCODE_AGENT_FOLDER="$HOME/.vscode-tunnel" ~/.local/share/vscode-cli/bin/code \
  tunnel user login --provider github
```

Prefer Microsoft login? Swap the provider:

```bash
VSCODE_AGENT_FOLDER="$HOME/.vscode-tunnel" ~/.local/share/vscode-cli/bin/code \
  tunnel user login --provider microsoft
```

Steps:
1) The CLI prints a device code and URL (GitHub: https://github.com/login/device, Microsoft: https://microsoft.com/devicelogin). Open it in a browser, paste the code, and sign in.
2) Once the CLI shows the tunnel is ready, press `Ctrl+C` to exit (systemd will handle it afterwards).
3) Restart the service so it takes over: `systemctl --user restart vscode-tunnel.service`

## Operations
- Check status: `systemctl --user status vscode-tunnel.service`
- View logs: `journalctl --user -u vscode-tunnel.service -f`
- Restart: `systemctl --user restart vscode-tunnel.service`
- Stop: `systemctl --user stop vscode-tunnel.service`
- Re-run setup: `./scripts/setup_vscode_tunnel.sh`
- Service file: `~/.config/systemd/user/vscode-tunnel.service` (source in `systemd/vscode-tunnel.service`)

## Connect from a browser
- Go to `https://vscode.dev/tunnel/dev-vm` (you must sign in with the same Microsoft account used during device login).
- Alternatively, in desktop VS Code choose “Remote Tunnels” and connect to `dev-vm`.
- Extensions and workspace data stay on this VM; outbound tunnel only.

## Troubleshooting
- **Service fails to start / restart loops**: Sign in once using the device-code command above, then `systemctl --user restart vscode-tunnel.service`.
- **CLI missing**: `./scripts/setup_vscode_tunnel.sh` will re-install the VS Code CLI into `~/.local/share/vscode-cli` and refresh the symlink `~/.local/bin/code`.
- **Stale state**: If you need a clean slate, stop the service, remove `~/.vscode-tunnel` (tokens live here), then re-run the setup and login steps.
- **Boot start not happening**: Ensure lingering is on: `loginctl show-user "$USER" -p Linger` should be `yes`. If not, run `sudo loginctl enable-linger "$USER"`.
- **Logs**: `journalctl --user -u vscode-tunnel.service -n 200 --no-pager` shows startup errors.
- **Need a fresh device code**: `systemctl --user restart vscode-tunnel.service` then `journalctl --user -u vscode-tunnel.service -f` to get the new code.

## Smoke test checklist
- `./scripts/setup_vscode_tunnel.sh` completes without errors and enables the user service.
- `systemctl --user status vscode-tunnel.service` shows `active (running)`.
- `journalctl --user -u vscode-tunnel.service -n 20 --no-pager` shows the tunnel listening without auth errors.
- From another machine/browser, `https://vscode.dev/tunnel/dev-vm` opens and connects to this VM.
- Stopping the service works: `systemctl --user stop vscode-tunnel.service`, then start again with `systemctl --user start vscode-tunnel.service`.
