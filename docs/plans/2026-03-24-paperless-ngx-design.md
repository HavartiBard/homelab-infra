# Paperless-NGX Deployment Design

**Date:** 2026-03-24
**Branch:** feature/paperless-ngx
**Status:** Approved

## Overview

Deploy [paperless-ngx](https://docs.paperless-ngx.com/) as a first-class homelab service on Unraid, exposed via NPM at `paperless.klsll.com`, with iCloud IMAP email ingestion.

## Architecture

### Components

Four containers on a single `paperless-net` bridge network:

| Container | Image | Role |
|---|---|---|
| `paperless-redis` | `redis:7-alpine` | Celery broker |
| `paperless-db` | `postgres:16-alpine` | Primary database |
| `paperless-web` | `ghcr.io/paperless-ngx/paperless-ngx:latest` | Web UI + API |
| `paperless-worker` | same image, worker command | Async document processing + email ingestion |

- Port `8000` exposed on Unraid (`192.168.20.14:8000`)
- Reverse-proxied by NPM to `paperless.klsll.com`

### Storage Layout

Bind-mounted to existing Unraid `paperless` share:

```
/mnt/user/paperless/
  data/        ← paperless index + database files
  media/       ← stored document archive
  consume/     ← drop folder for auto-import
  export/      ← export dumps
```

Compose stack deployed to `/opt/docker/paperless/`.

## Secrets

Stored in `ansible/group_vars/all/vault.yml`:

| Vault var | Purpose |
|---|---|
| `vault_paperless_secret_key` | Django secret key (random 50-char) |
| `vault_paperless_db_password` | PostgreSQL password |
| `vault_paperless_admin_password` | Initial admin UI password |
| `vault_paperless_email_host` | IMAP server (`imap.mail.me.com`) |
| `vault_paperless_email_user` | `james@klsll.com` |
| `vault_paperless_email_password` | iCloud app password (from 1Password: `Apple - Paperless`) |

## Role Defaults (Non-Secret Config)

```yaml
paperless_admin_user: admin
paperless_port: 8000
paperless_time_zone: America/Phoenix
paperless_ocr_language: eng
paperless_email_port: 993
paperless_email_security: SSL
paperless_email_from_email: james@klsll.com
paperless_appdata_dir: /mnt/user/paperless
paperless_compose_dir: /opt/docker/paperless
```

## File Structure

```
ansible/
  roles/paperless/
    defaults/main.yml
    tasks/main.yml
    templates/
      docker-compose.yml.j2
      paperless.env.j2
  playbooks/misc/deploy-paperless.yml
  files/npm/services/paperless.yml
  group_vars/all/vault.yml        ← 6 new entries
```

## Deployment Flow

1. Add 6 vault entries (read email app password from 1Password at vault-edit time)
2. Create directories: `/mnt/user/paperless/{data,media,consume,export}` and `/opt/docker/paperless/`
3. Render and write `docker-compose.yml` + `paperless.env` (chmod 600)
4. `docker compose pull && docker compose up -d`
5. Healthcheck on `http://192.168.20.14:8000/`
6. Print summary

## Email Ingestion

- Protocol: IMAP SSL
- Host: `imap.mail.me.com:993`
- User: `james@klsll.com`
- Password: iCloud app password (1Password: `op://AI Wedge/Apple - Paperless/credential`)
- Configured via `PAPERLESS_EMAIL_*` env vars on the worker container
- Paperless polls IMAP on a schedule; consumed messages moved to a `[paperless]` folder

## NPM Proxy

Service config at `ansible/files/npm/services/paperless.yml`:
- Upstream: `http://192.168.20.14:8000`
- Public URL: `https://paperless.klsll.com`

## Health Check

```bash
curl -sf http://192.168.20.14:8000/ && echo healthy
```

## Rollback

```bash
cd /opt/docker/paperless && docker compose down
# Data preserved in /mnt/user/paperless — no data loss on container removal
```
