# Ubuntu Bootstrap Playbook

Use this playbook to treat a fresh Ubuntu machine like the `dev-environment` container:
it installs `zsh`, Oh My Zsh with your preferred plugins, copies the curated `zshrc`, drops
`.env_container` from the vault, and staggers SSH keys so you can log in with
`~/.ssh/id_ed25519_homelab`.

## When to run

1. Add the target host to `ansible/inventory/hosts.yml` with the correct `ansible_host` /
   `ansible_user` (typically `root` for first-boot).
2. Encrypt a host-specific vars file (see “Vault variables” below).
3. Run the playbook:

```bash
cd ansible
ansible-playbook playbooks/misc/bootstrap-ubuntu.yml \
  -e target_hosts=ubuntu-01 \
  -e bootstrap_user=james
```

`target_hosts` is required and accepts comma-separated hostnames because the playbook stops
hosts that are not listed. `bootstrap_user` defaults to the connection user (`ansible_user`)
but you can override it if you want to create or configure another login.

## What gets configured

- Installs system packages: `git`, `zsh`, `curl`, `openssh-server`, `1password-cli`, etc.
- Adds the 1Password Debian repository plus its debsig policy.
- Ensures your jump user exists, belongs to `sudo`, and has `/bin/zsh` as the login shell.
- Clones Oh My Zsh, the Pure theme, and the autosuggestion/highlighting plugins under `/opt/oh-my-zsh`.
- Drops a templated `zshrc` (same structure as the dev container) under `/etc/skel` and
  copies it into the user’s home.
- Writes `~/.env_container` from `ubuntu_env_container_vars` so the shell sources every
  secret/API key you care about.
- Ensures `~/.bashrc` loads `.env_container` and advertises the `GOPATH`/`PATH` defaults.
- Deploys your controller’s `~/.ssh/id_ed25519_homelab.pub` into the user’s `authorized_keys`.
- Starts `sshd` and pins the system timezone to `America/Phoenix`.

## Vault variables (`ubuntu_env_container_vars`)

Store per-host `.env_container` data in an encrypted host vars file (e.g., `ansible/host_vars/ubuntu-01.yml`):

```yaml
ubuntu_env_container_vars:
  TZ: America/Phoenix
  OPENROUTER_API_KEY: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      1234...
  OP_SERVICE_ACCOUNT_TOKEN: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      5678...
  LMSTUDIO_BASE_URL: https://spraycheese.lab.klsll.com:1234/v1
```

Any key you add here is rendered inside `~/.env_container`, automatically quoted, and sourced by your shell.
Keep the file encrypted with `ansible-vault encrypt` and never hard-code secrets in the repo.

### Helper script

To simplify building the vaulted map from your existing `~/.env_container`, run the helper:

```bash
./scripts/generate-ubuntu-env-vault.py <hostname> --vault
```

Pass the inventory hostname (`ansible/inventory/hosts.yml`) and the script will:

1. Parse `~/.env_container` for `export KEY="value"` entries.
2. Emit `ansible/host_vars/<hostname>.yml` with `ubuntu_env_container_vars`.
3. Invoke `ansible-vault encrypt` so you only enter the password once.

Repeat the command whenever the source env file changes; the playbook will use the updated vault map to rewrite `~/.env_container` on the target host.

## Verification

After the playbook:

```bash
ssh james@<host> -i ~/.ssh/id_ed25519_homelab
zsh --version
ls ~/.env_container
op --version
cat ~/.zshrc | grep env_container
systemctl status ssh
```

Confirm the `.env_container` contains the values from the vault and that any CLI (e.g., `op`) runs without prompting for additional setup.

## Rollback

If something looks wrong, rerun the playbook under `--check` after you fix the offending vars, or remove `~/.zshrc`, `.env_container`, and `/opt/oh-my-zsh` manually and rerun.
