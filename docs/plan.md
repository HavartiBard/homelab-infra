# Homelab Infrastructure Plan

## Overview

This document describes the architecture for managing Docker containers across a hybrid homelab environment using **Portainer** as the single-pane-of-glass management interface.

## Target Platforms

| Platform | Role | Agent Type | Availability |
|----------|------|------------|--------------|
| **Proxmox VM** | Platform VM (Portainer Server) | Local Docker | Always-on |
| **Unraid** | Primary NAS + Docker host | Portainer Agent | Always-on |
| **Proxmox Docker VMs** | Additional Linux workloads | Portainer Agent | Always-on |
| **Windows Gaming PCs** | GPU compute workers (WSL2) | Edge Agent | On-demand |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           LAN / VPN Only                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌─────────────────────┐                                            │
│   │   Platform VM       │◄─── Portainer Server (9443)                │
│   │   (Proxmox)         │     NPM (80/443/81)                        │
│   │                     │     Technitium DNS (53/5380)               │
│   │                     │     Uptime Kuma (3001)                     │
│   └─────────┬───────────┘                                            │
│             │                                                         │
│   ┌─────────┴───────────────────────────────────────────────┐       │
│   │                    Portainer Agents                      │       │
│   ├─────────────────┬─────────────────┬─────────────────────┤       │
│   │                 │                 │                     │       │
│   ▼                 ▼                 ▼                     ▼       │
│ ┌─────────┐   ┌─────────┐   ┌─────────────┐   ┌─────────────────┐  │
│ │ Unraid  │   │ Prox VM │   │ Prox VM 2   │   │ WSL2 Worker     │  │
│ │ Agent   │   │ Agent   │   │ Agent       │   │ Edge Agent      │  │
│ │ :9001   │   │ :9001   │   │ :9001       │   │ (tunnel)        │  │
│ └─────────┘   └─────────┘   └─────────────┘   └─────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Stacks

### Platform Stack (`stacks/platform/`)
Core infrastructure services deployed to Platform VM:
- **Portainer CE** - Container management UI
- **Nginx Proxy Manager** - Reverse proxy with Let's Encrypt
- **Technitium DNS** - Local DNS server
- **Uptime Kuma** - Status monitoring

### GPU Worker Stack (`stacks/gpu-worker/`)
AI/ML workloads deployed to WSL2 workers:
- **Ollama** - LLM inference server
- **Open WebUI** - Chat interface

### Monitoring Stack (`stacks/monitoring/`)
Observability services:
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards
- **Node Exporter** - Host metrics
- **cAdvisor** - Container metrics

## Key Principles

1. **Git as Source of Truth** - All stack definitions live in this repo; Portainer deploys from Git
2. **LAN-Only Access** - Portainer and management interfaces are never exposed publicly
3. **Environment-Driven Config** - Secrets via `.env` files, never committed to Git
4. **Agent Architecture** - Standard agents for always-on hosts, Edge agents for on-demand workers
5. **No Kubernetes (Yet)** - Pure Docker Compose until scale demands otherwise

## Security Constraints

- Docker sockets are **never exposed publicly**
- Portainer accessible only via LAN or VPN
- Agent ports (9001) restricted to Platform VM via firewall
- All credentials stored in 1Password, referenced via `.env` files
- TLS enabled for all production services via NPM

## Implementation Phases

### Phase 1: Platform VM Setup
1. Create Ubuntu/Debian VM on Proxmox with static DHCP
2. Install Docker and deploy Platform Stack
3. Configure firewall (UFW) to restrict access
4. Verify Portainer is accessible from LAN only

### Phase 2: Agent Deployment
1. Install Portainer Agent on Unraid
2. Install Portainer Agent on additional Proxmox VMs
3. Add all endpoints to Portainer with tags/groups
4. Verify all endpoints show "healthy"

### Phase 3: Edge Workers
1. Set up WSL2 on Windows gaming PCs
2. Install Docker and nvidia-container-toolkit
3. Deploy Edge Agent using Portainer-generated key
4. Deploy GPU Worker stack
5. Document "gaming toggle" procedure

### Phase 4: Observability
1. Deploy Monitoring Stack to Platform VM
2. Configure Prometheus targets for all hosts
3. Import Grafana dashboards
4. Set up Uptime Kuma monitors

## References

- [Portainer Documentation](https://docs.portainer.io/)
- [Nginx Proxy Manager](https://nginxproxymanager.com/)
- [Technitium DNS](https://technitium.com/dns/)
- [Ollama](https://ollama.ai/)
