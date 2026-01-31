# Docker / Portainer Stacks

This directory contains Docker Compose / Portainer stack definitions for the homelab.

- `netbox-unraid.yml` – NetBox + Postgres + Redis stack for Unraid.
- `openhands-unraid/` – OpenHands AI agent control plane for Unraid.
- `dev-environment/` – SSH-accessible dev container with Claude Code, opencode, and full dev tooling (macvlan on br0).

Stacks here are intended to be the **source of truth**. Portainer and Docker Desktop should reference these files rather than using ad‑hoc inline configs.
