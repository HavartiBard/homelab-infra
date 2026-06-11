# Docker Stacks

This directory contains Docker Compose stack definitions for the homelab.

- `openhands-unraid/` – OpenHands AI agent control plane for Unraid.
- `dev-environment/` – SSH-accessible dev container with Claude Code, opencode, full dev tooling, and an optional Tailscale sidecar profile (macvlan on br0).

Stacks here are intended to be the **source of truth**. Deploy with `docker compose` directly.
