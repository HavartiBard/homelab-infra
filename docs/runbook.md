# Homelab Infrastructure Runbook

**Executable step-by-step guide from zero to working homelab.**

## Prerequisites

- [ ] Proxmox VE installed and accessible
- [ ] Unraid server running with Docker enabled
- [ ] Windows gaming PC(s) with NVIDIA GPU for WSL2 workers (optional)
- [ ] Static DHCP reservations configured for all hosts (or static IPs)
- [ ] This repo cloned locally: `git clone <repo-url> homelab-infra`
- [ ] 1Password vault with credentials (recommended)

---

## Phase 1: Platform VM Setup (Proxmox)

### 1.1 Create the Platform VM

```bash
# On Proxmox host or via web UI, create VM:
# - Name: platform-vm
# - OS: Ubuntu 24.04 LTS or Debian 12
# - CPU: 2 cores minimum
# - RAM: 4GB minimum
# - Disk: 32GB minimum
# - Network: Bridge to LAN (vmbr0)
```

**Via Proxmox Web UI:**
1. Click "Create VM"
2. Set VM ID (e.g., 100) and Name (platform-vm)
3. Select Ubuntu 24.04 ISO
4. Set disk size (32GB+)
5. Set CPU (2 cores) and RAM (4096MB)
6. Set network bridge (vmbr0)
7. Complete wizard and start VM

### 1.2 Initial VM Configuration

```bash
# SSH into the new VM
ssh user@<platform-vm-ip>

# Update system
sudo apt update && sudo apt upgrade -y

# Set hostname
sudo hostnamectl set-hostname platform-vm

# Set timezone
sudo timedatectl set-timezone America/New_York

# Install essential tools
sudo apt install -y curl wget git htop net-tools
```

### 1.3 Install Docker

```bash
# Install Docker using official script
curl -fsSL https://get.docker.com | sudo sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Enable Docker to start on boot
sudo systemctl enable docker

# Log out and back in for group changes
exit
```

```bash
# Verify Docker installation
ssh user@<platform-vm-ip>
docker --version
docker compose version
docker run hello-world
```

### 1.4 Configure DNS Resolution

```bash
# Point to your DNS servers (Technitium LXCs or fallback)
# Note: Technitium/AdGuard are deployed to dedicated LXCs via Ansible,
# not on Platform VM. See: ansible/playbooks/dns/provision-dns-dhcp-services.yml
sudo rm /etc/resolv.conf
echo "nameserver 192.168.20.2" | sudo tee /etc/resolv.conf    # tt1
echo "nameserver 192.168.20.3" | sudo tee -a /etc/resolv.conf # tt2
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf      # fallback

# Prevent NetworkManager from overwriting
sudo chattr +i /etc/resolv.conf
```

### 1.5 Configure Firewall (UFW)

```bash
# Install UFW if not present
sudo apt install -y ufw

# Allow SSH from LAN
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp

# NPM public ports (for reverse proxy)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# NPM Admin (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 81 proto tcp

# Monitoring UIs (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 3000 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 3001 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 9090 proto tcp

# Enable firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable

# Verify rules
sudo ufw status verbose
```

### 1.6 Clone Repository and Deploy Platform Stack

```bash
# Clone the repo
cd ~
git clone <your-repo-url> homelab-infra
cd homelab-infra/stacks/platform

# Create .env from template
cp .env.example .env

# Generate secure passwords and edit .env
# Use: openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32
nano .env
```

**Required .env values to set:**
- `NPM_DB_ROOT_PASSWORD` - MariaDB root password
- `NPM_DB_PASSWORD` - NPM database user password

```bash
# Validate compose file
docker compose config

# Deploy the stack
docker compose up -d

# Watch logs for startup
docker compose logs -f
```

### 1.7 Verify Platform Stack

```bash
# Check all containers are running
docker compose ps

# Expected output: all containers "Up" with (healthy) status
```

**Access the services:**

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| NPM | http://platform-vm-ip:81 | admin@example.com / changeme |
| Uptime Kuma | http://platform-vm-ip:3001 | Create admin on first login |

**Note:** DNS (Technitium/AdGuard) runs on dedicated LXCs (tt1/tt2, agh1/agh2), not Platform VM.
See Phase 4 or `ansible/playbooks/dns/provision-dns-dhcp-services.yml` for DNS deployment.

**First-time setup tasks:**
1. **NPM:** Change default admin email/password immediately
2. **Uptime Kuma:** Create admin account

---

## Phase 2: WSL2 GPU Worker Setup

### 3.1 Enable WSL2 on Windows

```powershell
# Run PowerShell as Administrator
wsl --install

# If already installed, update
wsl --update

# Set WSL2 as default
wsl --set-default-version 2

# Restart Windows when prompted
```

### 3.2 Install Ubuntu in WSL2

```powershell
# Install Ubuntu
wsl --install -d Ubuntu-24.04

# Launch and create user when prompted
wsl -d Ubuntu-24.04
```

### 3.3 Install Docker in WSL2

```bash
# Inside WSL2 Ubuntu
# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add user to docker group
sudo usermod -aG docker $USER

# Start Docker daemon
sudo service docker start

# Make Docker start automatically (add to ~/.bashrc)
echo 'sudo service docker start' >> ~/.bashrc

# Exit and re-enter WSL2
exit
```

```powershell
wsl -d Ubuntu-24.04
```

```bash
# Verify Docker
docker run hello-world
```

### 3.4 Install NVIDIA Container Toolkit

```bash
# Add NVIDIA repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo service docker restart
```

### 3.5 Verify GPU Access

```bash
# Check nvidia-smi works in WSL2
nvidia-smi

# Test GPU access in container
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

Expected output: GPU information showing your graphics card.

### 3.6 Deploy GPU Worker Stack

```bash
# Clone repo in WSL2
cd ~
git clone <your-repo-url> homelab-infra
cd homelab-infra/stacks/gpu-worker

# Create .env
cp .env.example .env
nano .env

# Deploy
docker compose up -d

# Verify GPU is accessible
docker compose logs ollama
```

### 3.8 Verify GPU Worker

```bash
# Check containers
docker compose ps

# Test Ollama API
curl http://localhost:11434/api/tags

# Pull a model
docker exec -it ollama ollama pull llama3.2:1b

# Test inference
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:1b",
  "prompt": "Hello, world!",
  "stream": false
}'
```

Access Open WebUI at `http://<wsl2-ip>:8080`

### 3.9 Gaming Toggle

To quickly stop GPU workloads for gaming:

**From WSL2 command line:**

```bash
# Stop for gaming
cd ~/homelab-infra/stacks/gpu-worker
docker compose stop

# Start after gaming
docker compose start
```

**Option C: Use the toggle script**

```bash
# Copy script to WSL2
~/homelab-infra/scripts/gaming-toggle.sh stop
~/homelab-infra/scripts/gaming-toggle.sh start
```

---

## Phase 3: Monitoring Stack Deployment

### 3.1 Deploy Monitoring Stack

```bash
cd stacks/monitoring
cp .env.example .env
# Edit .env and set GRAFANA_ADMIN_PASSWORD
docker compose up -d
```

### 3.2 Configure Prometheus Targets

After deployment, edit `prometheus.yml` to add your hosts:

```bash
# SSH to Platform VM
cd ~/homelab-infra/stacks/monitoring

# Edit prometheus.yml
nano prometheus.yml

# Uncomment and configure targets for:
# - Unraid node_exporter
# - Other Proxmox VMs
# - GPU workers

# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload
```

### 3.3 Import Grafana Dashboards

1. Access Grafana at `http://platform-vm-ip:3000`
2. Login with admin credentials
3. Go to **Dashboards** → **Import**
4. Import these community dashboards:
   - **1860** - Node Exporter Full
   - **893** - Docker/cAdvisor
5. Select Prometheus as datasource

### 3.4 Configure Uptime Kuma Monitors

1. Access Uptime Kuma at `http://platform-vm-ip:3001`
2. Add monitors for:
   - NPM: `http://localhost:81`
   - Technitium (tt1): `http://192.168.20.2:5380`
   - AdGuard (agh1): `http://192.168.20.4:3000`
   - External services you care about

---

## Phase 4: DNS and Reverse Proxy Configuration

### 4.1 Deploy DNS Infrastructure via Ansible

DNS (Technitium/AdGuard) is provisioned to dedicated LXCs via Ansible, not Platform VM.

```bash
cd ansible

# Required environment variables
export PROXMOX_API_HOST="192.168.20.100"
export PROXMOX_API_USER="root@pam"
export PROXMOX_API_TOKEN_ID="root@pam!ansible"
export PROXMOX_API_TOKEN_SECRET="<your-token-secret>"
export TECHNITIUM_ADMIN_PASSWORD="<strong-password>"
export LAB_ROOT_PASSWORD="<strong-password>"

# Deploy DNS/DHCP LXCs + services
ansible-playbook ansible/playbooks/dns/provision-dns-dhcp.yml --check --diff
ansible-playbook ansible/playbooks/dns/provision-dns-dhcp.yml --diff

# Deploy DNS service configs
ansible-playbook ansible/playbooks/dns/provision-dns-dhcp-services.yml --check --diff
ansible-playbook ansible/playbooks/dns/provision-dns-dhcp-services.yml --diff
```

See `ansible/playbooks/dns/provision-dns-dhcp-services.yml` and `ansible/files/dns/` for compose templates.

### 4.2 Configure Technitium as Authoritative DNS

1. Access Technitium at `http://192.168.20.2:5380` (tt1) or `http://192.168.20.3:5380` (tt2)
2. Go to **Zones** → **Add Zone**
3. Create zone for your domain (e.g., `klsll.com`)
4. Add A records for your services across VLANs:
   - `npm.lab.klsll.com` → Platform VM IP
   - etc.

See **Homelab Tests > Technitium DNS config checklist** (below) for detailed setup.

### 4.3 Configure Router DHCP

Update your router's DHCP settings to use Technitium/AdGuard as DNS:
- Primary DNS: `192.168.20.2` (tt1 Technitium)
- Secondary DNS: `192.168.20.3` (tt2 Technitium)
- Fallback: `1.1.1.1` (external)

### 4.4 Configure NPM Proxy Hosts

1. Access NPM at `http://platform-vm-ip:81`
2. Add Proxy Hosts for each service:

| Domain | Forward Hostname | Forward Port | SSL |
|--------|------------------|--------------|-----|
| grafana.home.local | localhost | 3000 | Let's Encrypt* |
| status.home.local | localhost | 3001 | Let's Encrypt* |

*For LAN-only services, you can use self-signed certs or HTTP.

#### 4.4.1 Automated service proxies

We keep the proxy/DNS definitions for key portals under `ansible/files/npm/services/`
and sync them to NPM with the matching playbooks:

| Playbook | Purpose |
|----------|---------|
| `ansible/playbooks/services/update-adguard-proxy.yml` | Publish `adguard.klsll.com` pointing to AdGuard HTTP UI via the wildcard cert (loaded from `ansible/files/npm/services/certificates.yml`) |
| `ansible/playbooks/services/update-dns-proxy.yml` | Publish `dns.klsll.com` so Technitium and DNS1/2 hostnames resolve through NPM |
| `ansible/playbooks/services/update-proxmox-proxy.yml` | Publish `pve.klsll.com` for the Proxmox web UI |
| `ansible/playbooks/services/update-unraid-proxy.yml` | Publish `unraid.klsll.com` for the Unraid web UI |

Each config ensures the vanity DNS name resolves to the NPM IP (192.168.20.50) so the UI traffic flows through the proxy stack and shares the wildcard certificate.

Run the applicable playbook any time you change the upstream port, move the service, or tweak certificate settings:

```bash
ansible-playbook ansible/playbooks/services/update-unraid-proxy.yml
ansible-playbook ansible/playbooks/services/update-adguard-proxy.yml
ansible-playbook ansible/playbooks/services/update-proxmox-proxy.yml
ansible-playbook ansible/playbooks/services/update-dns-proxy.yml
```

After the playbook completes, verify from any management host:

```bash
dig @192.168.20.50 adguard.klsll.com +short
curl -k https://pve.klsll.com
```

---

## Verification Checklist

### Platform VM
- [ ] Docker running: `docker ps`
- [ ] NPM accessible: `http://platform-vm-ip:81`
- [ ] Uptime Kuma accessible: `http://platform-vm-ip:3001`
- [ ] Firewall active: `sudo ufw status`

### DNS LXCs (tt1/tt2, agh1/agh2)
- [ ] Technitium DNS responding: `dig @192.168.20.2 google.com` (tt1)
- [ ] AdGuard accessible: `http://192.168.20.4:3000` (agh1)

### GPU Workers
- [ ] WSL2 Docker running
- [ ] NVIDIA GPU accessible: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
- [ ] GPU Worker stack deployed and healthy
- [ ] Ollama API responding: `curl http://localhost:11434/api/tags`

### Monitoring
- [ ] Prometheus scraping targets: `http://platform-vm-ip:9090/targets`
- [ ] Grafana dashboards loading
- [ ] Node metrics appearing

### Security
- [ ] No secrets in Git: `git grep -i password`
- [ ] Management interfaces not accessible from internet

---

## Rollback Procedures

### Stack Rollback

```bash
# Stop the stack
docker compose down

# Checkout previous version
git log --oneline -5
git checkout <previous-commit> -- stacks/<stack-name>/

# Redeploy
docker compose up -d
```

### Volume Data Backup/Restore

```bash
# Backup a volume
docker run --rm -v <volume-name>:/data -v $(pwd):/backup alpine \
  tar czf /backup/<volume-name>-backup.tar.gz -C /data .

# Restore a volume
docker run --rm -v <volume-name>:/data -v $(pwd):/backup alpine \
  sh -c "cd /data && tar xzf /backup/<volume-name>-backup.tar.gz"
```

### Full Platform Rollback

1. Stop all stacks: `docker compose down` in each stack directory
2. Restore volumes from backup
3. Checkout known-good commit
4. Redeploy stacks

---

## Troubleshooting

### Container won't start
```bash
docker compose logs <service-name>
docker inspect <container-name>
```

### Port already in use
```bash
sudo lsof -i :<port>
sudo netstat -tulpn | grep <port>
```

### DNS not resolving
```bash
# Check Technitium on tt1 LXC
ssh root@192.168.20.2
docker logs technitium

# Test DNS directly from tt1
dig @192.168.20.2 example.com

# Or from tt2 (secondary)
dig @192.168.20.3 example.com

# Verify /etc/resolv.conf on your host
cat /etc/resolv.conf
```

### GPU not detected in container
```bash
# Verify nvidia-smi works on host
nvidia-smi

# Check Docker NVIDIA runtime
docker info | grep -i nvidia

# Restart Docker
sudo service docker restart
```

---

## Homelab Tests

### DHCP VLAN smoke test (non-disruptive, netns)
Quick DHCP validation across VLANs using a temporary network namespace on a trunked Proxmox host. Does not touch host routes or DNS.

**Prereqs:** Run on a trunk port (enp1s0 here) that carries VLANs 1/20/30 tagged. Requires `dhclient` on the host.

```bash
sudo ip netns add dhcp-test
for vid in 1 20 30; do
  sudo ip link add link enp1s0 name enp1s0.${vid}-test type vlan id ${vid}
  sudo ip link set enp1s0.${vid}-test netns dhcp-test
  sudo ip netns exec dhcp-test ip link set lo up
  sudo ip netns exec dhcp-test ip link set enp1s0.${vid}-test up
  echo "Testing VLAN ${vid}"
  sudo ip netns exec dhcp-test timeout 15 dhclient -v -1 -sf /bin/true enp1s0.${vid}-test
  sudo ip netns exec dhcp-test ip addr show enp1s0.${vid}-test
  sudo ip netns exec dhcp-test dhclient -r enp1s0.${vid}-test || true
  sudo ip netns exec dhcp-test ip link set enp1s0.${vid}-test down
  sudo ip link delete enp1s0.${vid}-test
done
sudo ip netns del dhcp-test
```

**Success criteria:** Each VLAN shows a DHCPOFFER/ACK and a lease (e.g., from 192.168.X.1). The `execve (/bin/true)` warning is harmless.

**Adjustments:** Swap `enp1s0` for your trunk NIC; add/remove VLAN IDs in the loop as needed (e.g., include 40).

---

### Technitium DNS config checklist (tt1 primary, tt2 secondary)
Primary: tt1 (192.168.1.2/20.2/30.2) = `dns1`. Secondary: tt2 (192.168.1.3/20.3/30.3) = `dns2`.

- Zones (on tt1 as primary): keep apex `klsll.com` for vanity/external; add internal subdomains per VLAN: `lan.klsll.com` (VLAN1), `lab.klsll.com` (VLAN20), `iot.klsll.com` (VLAN30). Reverse zones: `1.168.192.in-addr.arpa`, `20.168.192.in-addr.arpa`, `30.168.192.in-addr.arpa` (add 40 if used). SOA MNAME `dns1.klsll.com`, RNAME admin email. NS: `dns1.klsll.com`, `dns2.klsll.com`.
- Replication: generate TSIG on tt1, allow AXFR/IXFR + NOTIFY to tt2 using that TSIG. On tt2 add secondary zones pointing to tt1 with the same TSIG; allow NOTIFY from tt1.
- DHCP (authoritative on tt1 only to avoid split-brain):
  - VLAN1 192.168.1.0/24 → `lan.klsll.com`: pool 192.168.1.100–199, lease 24h, router 192.168.1.1, DNS 192.168.1.2,192.168.1.3, set Option 15 to `lan.klsll.com`.
  - VLAN20 192.168.20.0/24 → `lab.klsll.com`: pool 192.168.20.100–199, lease 24h, router 192.168.20.1, DNS 192.168.1.2,192.168.1.3 (or 20.2/20.3), Option 15 `lab.klsll.com`.
  - VLAN30 192.168.30.0/24 → `iot.klsll.com`: pool 192.168.30.100–199, lease 24h, router 192.168.30.1, DNS 192.168.1.2,192.168.1.3 (or 30.2/30.3), Option 15 `iot.klsll.com`.
  - VLAN40 (guest, if used): pool 192.168.40.50–150, lease 8h, router 192.168.40.1, DNS 192.168.1.2,192.168.1.3 (or external 1.1.1.1 if isolating guest).
  - Enable DHCP → “Update DNS records” and “Use client supplied hostname”; enable PTRs; allow IP-based names if hostname missing. Reservations outside pools (e.g., .10–.49) for core infra (Unraid 192.168.20.14, Proxmox nodes, switches/APs, printers).
- Records: create `dns1.klsll.com` → tt1 IPs; `dns2.klsll.com` → tt2 IPs; add A/AAAA/CNAME for infra/services within the appropriate subdomains; PTRs in reverse zones. Enable recursion for LAN only; set upstreams (e.g., Cloudflare/Quad9); enable DNSSEC; restrict admin UI to mgmt/VPN; restrict AXFR to tt2 via TSIG.
- Validation: `dig @192.168.1.2 lan.klsll.com SOA`; `dig @192.168.1.3 lan.klsll.com SOA` (serial should match tt1); DHCP netns test (above) should get offers from tt1 with names under the subdomains once DHCP is enabled.

**Ansible role for Technitium (file-based sync)**
- Role: `ansible/roles/technitium` (syncs exported data dir to `/opt/dns/data/technitium`, optional restart).
- Export tt1 data to a local path and set `technitium_data_src` explicitly (default is null to avoid accidental bulk copies). Keep secrets in vault/1Password, then run role against tt1/tt2. See `roles/technitium/README.md` for usage and defaults.

---

## Maintenance Tasks

### Weekly
- [ ] Check Uptime Kuma for any alerts
- [ ] Review Grafana dashboards for anomalies
- [ ] Pull latest Git changes: `git pull`

### Monthly
- [ ] Update container images
- [ ] Review and rotate passwords if needed
- [ ] Backup all volumes
- [ ] Test rollback procedure

### Quarterly
- [ ] Review firewall rules
- [ ] Update base OS packages
- [ ] Review and clean up unused images/volumes

---

## Quick Reference

### Useful Commands

```bash
# View all containers across compose
docker compose ps

# View logs with timestamps
docker compose logs -f --timestamps

# Restart a service
docker compose restart <service>

# Pull latest images and recreate
docker compose pull && docker compose up -d

# Clean up unused resources
docker system prune -af

# Backup all volumes
./scripts/backup-volumes.sh
```

### Important Paths

| Host | Path | Purpose |
|------|------|---------|
| Platform VM | ~/homelab-infra | Git repo |
| Unraid | /mnt/user/appdata | Container data |
| WSL2 | ~/homelab-infra | Git repo |

### Key URLs

| Service | URL | Host |
|---------|-----|------|
| NPM Admin | http://platform-vm:81 | Platform VM |
| Uptime Kuma | http://platform-vm:3001 | Platform VM |
| Grafana | http://platform-vm:3000 | Platform VM |
| Prometheus | http://platform-vm:9090 | Platform VM |
| Technitium DNS | http://192.168.20.2:5380 | tt1 (LXC) |
| AdGuard Home | http://192.168.20.4:3000 | agh1 (LXC) |
