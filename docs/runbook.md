# Homelab Infrastructure Runbook

**Executable step-by-step guide from zero to working Portainer-managed homelab.**

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

### 1.4 Disable systemd-resolved (Required for Technitium DNS)

```bash
# Stop and disable systemd-resolved
sudo systemctl disable --now systemd-resolved

# Remove the symlink and create static resolv.conf
sudo rm /etc/resolv.conf
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf

# Prevent NetworkManager from overwriting
sudo chattr +i /etc/resolv.conf
```

### 1.5 Configure Firewall (UFW)

```bash
# Install UFW if not present
sudo apt install -y ufw

# Allow SSH from LAN
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp

# Portainer (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 9443 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 9000 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 8000 proto tcp

# NPM public ports (for reverse proxy)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# NPM Admin (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 81 proto tcp

# DNS (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 53

# Technitium Admin (LAN only)
sudo ufw allow from 192.168.0.0/16 to any port 5380 proto tcp

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
- `TECHNITIUM_ADMIN_PASSWORD` - DNS admin password

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
| Portainer | https://platform-vm-ip:9443 | Create admin on first login |
| NPM | http://platform-vm-ip:81 | admin@example.com / changeme |
| Technitium | http://platform-vm-ip:5380 | admin / (set in .env) |
| Uptime Kuma | http://platform-vm-ip:3001 | Create admin on first login |

**First-time setup tasks:**
1. **Portainer:** Create admin account, save password in 1Password
2. **NPM:** Change default admin email/password immediately
3. **Technitium:** Verify DNS is responding: `dig @<platform-vm-ip> google.com`
4. **Uptime Kuma:** Create admin account

---

## Phase 2: Portainer Agent Deployment

### 2.1 Add Local Environment in Portainer

1. Open Portainer at `https://platform-vm-ip:9443`
2. The local Docker environment should appear automatically
3. Click on it and verify containers are visible

### 2.2 Install Portainer Agent on Unraid

**Option A: Via Unraid Docker UI**

1. Go to Unraid web UI → Docker → Add Container
2. Use these settings:
   - **Name:** portainer-agent
   - **Repository:** portainer/agent:2.21.4
   - **Network:** bridge
   - **Port:** 9001 → 9001
   - **Path:** /var/run/docker.sock → /var/run/docker.sock
   - **Path:** /var/lib/docker/volumes → /var/lib/docker/volumes

**Option B: Via SSH/Command Line**

```bash
# SSH into Unraid
ssh root@<unraid-ip>

# Run Portainer Agent
docker run -d \
  --name portainer-agent \
  --restart always \
  -p 9001:9001 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/docker/volumes:/var/lib/docker/volumes \
  portainer/agent:2.21.4
```

**Option C: Use the install script**

```bash
# From this repo
./scripts/install-portainer-agent.sh
```

### 2.3 Add Unraid Endpoint to Portainer

1. In Portainer, go to **Environments** → **Add Environment**
2. Select **Agent**
3. Enter:
   - **Name:** Unraid
   - **Environment URL:** `<unraid-ip>:9001`
4. Click **Connect**
5. Verify status shows "Up" with green indicator

### 2.4 Install Agent on Additional Proxmox Docker VMs

For each additional Docker VM:

```bash
# SSH into the VM
ssh user@<vm-ip>

# Run Portainer Agent
docker run -d \
  --name portainer-agent \
  --restart always \
  -p 9001:9001 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/docker/volumes:/var/lib/docker/volumes \
  portainer/agent:2.21.4

# Configure firewall to only allow Platform VM
sudo ufw allow from <platform-vm-ip> to any port 9001 proto tcp
sudo ufw enable
```

Add each endpoint in Portainer using the same process as Unraid.

### 2.5 Configure Endpoint Groups and Tags

1. In Portainer, go to **Environments**
2. For each endpoint, click **Edit**
3. Add **Tags** (e.g., `always-on`, `gpu-worker`, `nas`, `proxmox`)
4. Create **Groups** for organization:
   - **Always-On:** Platform VM, Unraid
   - **GPU Workers:** WSL2 endpoints
   - **Proxmox VMs:** Additional Docker VMs

### 2.6 Verify All Agents

```bash
# From Platform VM, test connectivity to each agent
curl -s http://<unraid-ip>:9001/api/agents | jq .
curl -s http://<proxmox-vm-ip>:9001/api/agents | jq .
```

All endpoints should show "Up" with green status in Portainer.

---

## Phase 3: WSL2 GPU Worker Setup

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

### 3.6 Deploy Portainer Edge Agent

1. In Portainer, go to **Environments** → **Add Environment**
2. Select **Edge Agent**
3. Enter:
   - **Name:** GPU-Worker-1 (or descriptive name)
   - **Portainer Server URL:** `https://<platform-vm-ip>:9443`
4. Click **Create**
5. Copy the generated Edge Agent command

```bash
# In WSL2, run the Edge Agent (example - use YOUR generated command)
docker run -d \
  --name portainer-edge-agent \
  --restart always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/docker/volumes:/var/lib/docker/volumes \
  -v /:/host \
  -v portainer_agent_data:/data \
  -e EDGE=1 \
  -e EDGE_ID=<your-edge-id> \
  -e EDGE_KEY=<your-edge-key> \
  -e EDGE_INSECURE_POLL=1 \
  portainer/agent:2.21.4
```

### 3.7 Deploy GPU Worker Stack

**Option A: Deploy from Portainer UI (Recommended)**

1. In Portainer, select the GPU Worker environment
2. Go to **Stacks** → **Add Stack**
3. Select **Repository**
4. Enter:
   - **Name:** gpu-worker
   - **Repository URL:** `<your-git-repo-url>`
   - **Branch:** main
   - **Compose path:** stacks/gpu-worker/compose.yml
5. Add environment variables from `.env.example`
6. Click **Deploy the stack**

**Option B: Deploy locally in WSL2**

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

**Option A: From Portainer UI**
1. Go to GPU Worker environment
2. Select gpu-worker stack
3. Click **Stop**
4. When done gaming, click **Start**

**Option B: From WSL2 command line**

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

## Phase 4: Deploy Stacks from Git in Portainer

### 4.1 Configure Git Repository in Portainer

1. Go to **Settings** → **Authentication** (if using private repo)
2. Add Git credentials if needed

### 4.2 Deploy Stack from Git

1. Select target environment (e.g., Platform VM)
2. Go to **Stacks** → **Add Stack**
3. Select **Repository**
4. Configure:
   - **Name:** Choose a name (e.g., `monitoring`)
   - **Repository URL:** Your Git repo URL
   - **Branch:** `main`
   - **Compose path:** `stacks/monitoring/compose.yml`
   - **GitOps updates:** Enable for auto-sync (optional)
5. **Environment variables:** Add from `.env.example`
   - Click "Add environment variable" for each required var
   - Or use "Load variables from .env file" if supported
6. Click **Deploy the stack**

### 4.3 Handling Environment Variables and Secrets

**DO NOT commit secrets to Git.** Instead:

1. Store secrets in 1Password
2. When deploying in Portainer, manually enter env vars
3. Portainer encrypts and stores them securely

For automation, consider:
- Portainer's built-in secret management
- External secret stores (HashiCorp Vault, etc.)

---

## Phase 5: Monitoring Stack Deployment

### 5.1 Deploy Monitoring Stack

1. In Portainer, select Platform VM environment
2. Go to **Stacks** → **Add Stack** → **Repository**
3. Configure:
   - **Name:** monitoring
   - **Repository URL:** Your repo URL
   - **Compose path:** stacks/monitoring/compose.yml
4. Add environment variables:
   - `GRAFANA_ADMIN_PASSWORD` (required)
   - Other vars from `.env.example`
5. Deploy

### 5.2 Configure Prometheus Targets

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

### 5.3 Import Grafana Dashboards

1. Access Grafana at `http://platform-vm-ip:3000`
2. Login with admin credentials
3. Go to **Dashboards** → **Import**
4. Import these community dashboards:
   - **1860** - Node Exporter Full
   - **893** - Docker/cAdvisor
   - **11462** - Portainer
5. Select Prometheus as datasource

### 5.4 Configure Uptime Kuma Monitors

1. Access Uptime Kuma at `http://platform-vm-ip:3001`
2. Add monitors for:
   - Portainer: `https://localhost:9443`
   - NPM: `http://localhost:81`
   - Technitium: `http://localhost:5380`
   - Each agent endpoint
   - External services you care about

---

## Phase 6: DNS and Reverse Proxy Configuration

### 6.1 Configure Technitium as LAN DNS

1. Access Technitium at `http://platform-vm-ip:5380`
2. Go to **Zones** → **Add Zone**
3. Create zone for your domain (e.g., `home.local`)
4. Add A records for your services:
   - `portainer.home.local` → Platform VM IP
   - `npm.home.local` → Platform VM IP
   - `grafana.home.local` → Platform VM IP
   - etc.

### 6.2 Configure Router DHCP

Update your router's DHCP settings to use Platform VM as DNS:
- Primary DNS: `<platform-vm-ip>`
- Secondary DNS: `1.1.1.1` (fallback)

### 6.3 Configure NPM Proxy Hosts

1. Access NPM at `http://platform-vm-ip:81`
2. Add Proxy Hosts for each service:

| Domain | Forward Hostname | Forward Port | SSL |
|--------|------------------|--------------|-----|
| portainer.home.local | localhost | 9443 | Let's Encrypt* |
| grafana.home.local | localhost | 3000 | Let's Encrypt* |
| status.home.local | localhost | 3001 | Let's Encrypt* |

*For LAN-only services, you can use self-signed certs or HTTP.

---

## Verification Checklist

### Platform VM
- [ ] Docker running: `docker ps`
- [ ] Portainer accessible: `https://platform-vm-ip:9443`
- [ ] NPM accessible: `http://platform-vm-ip:81`
- [ ] Technitium DNS responding: `dig @platform-vm-ip google.com`
- [ ] Uptime Kuma accessible: `http://platform-vm-ip:3001`
- [ ] Firewall active: `sudo ufw status`

### Agents
- [ ] Unraid agent connected in Portainer
- [ ] All Proxmox VM agents connected
- [ ] All endpoints show "healthy" status

### GPU Workers
- [ ] WSL2 Docker running
- [ ] NVIDIA GPU accessible: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
- [ ] Edge Agent connected in Portainer
- [ ] GPU Worker stack deployed and healthy
- [ ] Ollama API responding: `curl http://localhost:11434/api/tags`

### Monitoring
- [ ] Prometheus scraping targets: `http://platform-vm-ip:9090/targets`
- [ ] Grafana dashboards loading
- [ ] Node metrics appearing

### Security
- [ ] No secrets in Git: `git grep -i password`
- [ ] Portainer not accessible from internet
- [ ] Agent ports only accessible from Platform VM

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

### Edge Agent Reconnection

If Edge Agent loses connection:

```bash
# In WSL2
docker logs portainer-edge-agent

# Restart agent
docker restart portainer-edge-agent

# If still failing, remove and redeploy with new edge key
docker rm -f portainer-edge-agent
# Re-run the edge agent command from Portainer
```

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
# Check Technitium is running
docker logs technitium-dns

# Test DNS directly
dig @localhost example.com

# Check /etc/resolv.conf
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

### Edge Agent not connecting
```bash
# Check agent logs
docker logs portainer-edge-agent

# Verify outbound connectivity
curl -v https://<platform-vm-ip>:8000

# Check edge key hasn't expired
# Generate new edge key in Portainer if needed
```

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
- [ ] Audit Portainer users and access
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

| Service | URL |
|---------|-----|
| Portainer | https://platform-vm:9443 |
| NPM Admin | http://platform-vm:81 |
| Technitium | http://platform-vm:5380 |
| Grafana | http://platform-vm:3000 |
| Uptime Kuma | http://platform-vm:3001 |
| Prometheus | http://platform-vm:9090 |
