# Network Ports Reference

## Overview

This document lists all ports used by homelab stacks with access requirements.

**Legend:**
- 🔒 **LAN-Only** - Must never be exposed to internet; use firewall rules
- 🌐 **Proxied** - Can be exposed via reverse proxy with authentication
- 🔐 **VPN** - Accessible only via VPN tunnel
- ⚠️ **Sensitive** - Contains management interface; extra caution required

---

## Platform Stack

| Service | Port | Protocol | Access | Description |
|---------|------|----------|--------|-------------|
| **Portainer** | 9443 | TCP/HTTPS | 🔒⚠️ LAN-Only | Admin UI (HTTPS) |
| Portainer | 9000 | TCP/HTTP | 🔒⚠️ LAN-Only | Admin UI (HTTP, disable in prod) |
| Portainer | 8000 | TCP | 🔒 LAN-Only | Edge Agent tunnel server |
| **NPM** | 80 | TCP | 🌐 Proxied | HTTP (redirect to HTTPS) |
| NPM | 443 | TCP | 🌐 Proxied | HTTPS reverse proxy |
| NPM | 81 | TCP | 🔒⚠️ LAN-Only | Admin UI |
| **Technitium** | 53 | UDP/TCP | 🔒 LAN-Only | DNS queries |
| Technitium | 5380 | TCP | 🔒⚠️ LAN-Only | Admin web UI |
| Technitium | 8443 | UDP | 🔒 LAN-Only | DNS-over-HTTPS (QUIC) |
| Technitium | 853 | TCP | 🔒 LAN-Only | DNS-over-TLS (optional) |
| **Uptime Kuma** | 3001 | TCP | 🌐 Proxied | Status page UI |

## Monitoring Stack

| Service | Port | Protocol | Access | Description |
|---------|------|----------|--------|-------------|
| **Prometheus** | 9090 | TCP | 🔒⚠️ LAN-Only | Metrics UI and API |
| **Grafana** | 3000 | TCP | 🌐 Proxied | Dashboards UI |
| **Node Exporter** | 9100 | TCP | 🔒 LAN-Only | Host metrics endpoint |
| **cAdvisor** | 8081 | TCP | 🔒 LAN-Only | Container metrics |

## GPU Worker Stack

| Service | Port | Protocol | Access | Description |
|---------|------|----------|--------|-------------|
| **Ollama** | 11434 | TCP | 🔒 LAN-Only | LLM API endpoint |
| **Open WebUI** | 8080 | TCP | 🌐 Proxied | Chat interface |

## Agent Ports

| Service | Port | Protocol | Access | Description |
|---------|------|----------|--------|-------------|
| **Portainer Agent** | 9001 | TCP | 🔒 LAN-Only | Agent communication |
| **Edge Agent** | (outbound) | TCP | 🔒 Outbound | Tunnels to Portainer :8000 |

## Existing Services (Reference)

| Service | Port | Protocol | Access | Description |
|---------|------|----------|--------|-------------|
| **NetBox** | 8001 | TCP | 🌐 Proxied | DCIM/IPAM |
| **1Password MCP** | 6975 | TCP | 🔒 LAN-Only | MCP server |
| **Homelab MCP** | 6971 | TCP | 🔒 LAN-Only | MCP server (Orbi, NPM, etc.) |
| **AdGuard Home** | 53 | UDP/TCP | 🔒 LAN-Only | DNS queries |
| AdGuard Home | 3080 | TCP | 🔒⚠️ LAN-Only | Initial setup UI |
| AdGuard Home | 8053 | TCP | 🔒⚠️ LAN-Only | Web UI (HTTP) |
| AdGuard Home | 8853 | TCP | 🔒 LAN-Only | DNS-over-HTTPS |
| AdGuard Home | 853 | TCP | 🔒 LAN-Only | DNS-over-TLS |

---

## Firewall Rules (UFW Example)

### Platform VM - Allow Only

```bash
# SSH (from LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp

# Portainer (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 9443 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 9000 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 8000 proto tcp

# NPM (public for reverse proxy)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# NPM Admin (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 81 proto tcp

# DNS (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 53

# Technitium Admin (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 5380 proto tcp

# Monitoring (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 3000 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 3001 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 9090 proto tcp

# Enable firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

### Agent Hosts - Allow Only

```bash
# SSH (from LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp

# Portainer Agent (from Platform VM only)
sudo ufw allow from <PLATFORM_VM_IP> to any port 9001 proto tcp

# Node Exporter (from Platform VM only)
sudo ufw allow from <PLATFORM_VM_IP> to any port 9100 proto tcp

sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

---

## Port Conflict Notes

### DNS Port 53
- **Conflict:** Ubuntu's `systemd-resolved` uses port 53
- **Resolution:** Disable resolved or reconfigure
  ```bash
  sudo systemctl disable --now systemd-resolved
  sudo rm /etc/resolv.conf
  echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
  ```

### Grafana Port 3000
- **Conflict:** May conflict with other dev servers (React, etc.)
- **Resolution:** Change via `GRAFANA_PORT` env var

### NPM Port 443
- **Conflict:** Technitium DoH also uses 443/udp
- **Resolution:** Technitium DoH moved to 8443 in compose

---

## Recommended Reverse Proxy Hostnames

Configure these in NPM for internal access:

| Hostname | Target | Auth |
|----------|--------|------|
| `portainer.home.local` | localhost:9443 | Built-in |
| `npm.home.local` | localhost:81 | Built-in |
| `dns.home.local` | localhost:5380 | Built-in |
| `status.home.local` | localhost:3001 | Built-in |
| `grafana.home.local` | localhost:3000 | Built-in |
| `prometheus.home.local` | localhost:9090 | NPM Access List |
| `ollama.home.local` | <worker-ip>:11434 | NPM Access List |
| `chat.home.local` | <worker-ip>:8080 | Built-in |
| `netbox.home.local` | <unraid-ip>:8001 | Built-in |
| `adguard.home.local` | <unraid-ip>:8053 | Built-in |
