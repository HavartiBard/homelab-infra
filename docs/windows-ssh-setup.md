# Setting Up SSH on Windows GPU Worker (spraycheese)

This document explains how to enable SSH on the `spraycheese` Windows GPU worker so that other devices on the network can SSH in for remote management.

## Prerequisites

### 1. WinRM Must Be Enabled
The Ansible playbook uses WinRM to initially connect and install SSH. WinRM should be enabled by default on Windows Server but may need manual setup on Windows Pro/Home editions.

**Check WinRM Status:**
```powershell
winrm quickconfig
# If prompted, type 'Y' to enable
```

**Verify WinRM is listening:**
```powershell
winrm enumerate winrm/config/listener
```

### 2. Network Connectivity
- spraycheese (192.168.20.50) must be reachable from your management machine
- Port 5985 (WinRM HTTP) must be accessible from your management machine
- Port 22 (SSH) must be accessible from the LAN after setup

## Quick Start: Direct PowerShell Setup

**Fastest way (no WinRM required):**

1. Save the PowerShell script: `ansible/playbooks/windows/setup-ssh.ps1`
2. Copy your SSH public key to `C:\temp\id_ed25519_homelab.pub` on Windows
3. Run in PowerShell as Administrator:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   C:\Users\james\setup-ssh.ps1
   ```

See `WINDOWS_SSH_QUICKSTART.md` for complete instructions.

---

## Detailed Setup: SSH via WinRM (Ansible)

### Step 1: Ensure pywinrm is Installed

```bash
pip install pywinrm
# or if using venv:
source .venv-ansible/bin/activate  # if using virtual env
pip install pywinrm
```

### Step 2: Run the SSH Setup Playbook

```bash
cd ansible

# Set Windows credentials (required for WinRM connection)
export ANSIBLE_WINDOWS_USER='james'
export ANSIBLE_WINDOWS_PASSWORD='<your-windows-password>'

# Run the setup playbook
ansible-playbook playbooks/windows/setup-ssh.yml --limit spraycheese -v

# If you need to target all Windows hosts:
ansible-playbook playbooks/windows/setup-ssh.yml --limit windows_gpu -v
```

**What this playbook does:**
1. ✅ Installs OpenSSH Server (Windows optional component)
2. ✅ Starts and enables the `sshd` service to auto-start
3. ✅ Creates Windows Firewall rule to allow SSH (port 22)
4. ✅ Installs your SSH public key (`~/.ssh/id_ed25519_homelab.pub`) to authorized_keys
5. ✅ Configures sshd for key-based authentication only (disables passwords)
6. ✅ Validates configuration and verifies SSH is listening

### Step 3: Verify SSH Access

Once the playbook completes successfully, test SSH access:

```bash
# Test SSH connection
ssh -i ~/.ssh/id_ed25519_homelab james@192.168.20.50

# Or using Ansible
ansible -i ansible/inventory/hosts.yml -u james spraycheese -m ping
```

## Updating Ansible Inventory for SSH

After SSH is confirmed working, update the inventory to use SSH instead of WinRM:

### Option A: Update inventory/hosts.yml (Recommended)
```yaml
windows_gpu:
  hosts:
    spraycheese:
      ansible_host: 192.168.20.50
      ansible_user: james
      ansible_connection: ssh
      ansible_ssh_private_key_file: ~/.ssh/id_ed25519_homelab
```

### Option B: Override via group_vars
Update `ansible/group_vars/windows_gpu/main.yml`:
```yaml
---
# After SSH setup is complete, use SSH instead of WinRM
ansible_connection: ssh
ansible_ssh_private_key_file: ~/.ssh/id_ed25519_homelab
ansible_user: james
```

## Troubleshooting

### Issue: "Connection refused" or "Port 5985 not responding"
**Cause:** WinRM not enabled or not listening

**Solution:**
```powershell
# On Windows, run as Administrator:
winrm quickconfig
# Select 'Y' when prompted
```

### Issue: "Failed to install OpenSSH Server"
**Cause:** Windows Capability installation not available (possibly offline system or wrong Windows edition)

**Solution:** Install OpenSSH Server manually:
1. Open Settings → Apps → Optional Features
2. Click "View optional features"
3. Search for "OpenSSH"
4. Click "OpenSSH Server" → Install

### Issue: SSH connection works but Ansible fails with permission denied
**Cause:** SSH key or file permissions not set correctly

**Solution:** Run the playbook again - it includes permission fixes:
```bash
ansible-playbook playbooks/windows/setup-ssh.yml --limit spraycheese
```

### Issue: "AuthorizedKeysFile .ssh/authorized_keys" not recognized
**Cause:** Windows OpenSSH using different path format

**Solution:** The playbook handles this, but if manual config is needed, use:
```
AuthorizedKeysFile .ssh/authorized_keys
```
The `~` expansion works correctly on Windows OpenSSH.

## Manual SSH Setup (if Ansible/WinRM unavailable)

If you cannot use WinRM (e.g., it's disabled and you don't have local access), set up SSH manually via RDP or local console:

```powershell
# Run as Administrator

# 1. Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 2. Start the service
Start-Service sshd

# 3. Enable auto-start
Set-Service -Name sshd -StartupType 'Automatic'

# 4. Create .ssh directory
mkdir C:\Users\james\.ssh

# 5. Add your public key to authorized_keys
# (Copy content of ~/.ssh/id_ed25519_homelab.pub to C:\Users\james\.ssh\authorized_keys)

# 6. Set permissions
icacls C:\Users\james\.ssh /inheritance:r /grant:r "${env:COMPUTERNAME}\james:(OI)(CI)F"
icacls C:\Users\james\.ssh\authorized_keys /inheritance:r /grant:r "${env:COMPUTERNAME}\james:F"

# 7. Update sshd_config (C:\ProgramData\ssh\sshd_config)
# - Uncomment: PubkeyAuthentication yes
# - Set: PasswordAuthentication no
# - Set: PermitEmptyPasswords no
# - Add: AuthorizedKeysFile .ssh/authorized_keys

# 8. Restart SSH service
Restart-Service sshd

# 9. Verify SSH is listening
netstat -an | findstr :22
```

## Security Considerations

### Current Configuration
- ✅ **Public key authentication only** - Password login disabled
- ✅ **Firewall rule** - Windows Firewall allows port 22 (can be further restricted to specific IPs)
- ✅ **Proper permissions** - SSH keys have restricted file permissions

### Additional Hardening (Optional)
```powershell
# Restrict firewall rule to specific IP (e.g., 192.168.20.0/24)
Remove-NetFirewallRule -DisplayName "SSH Server (sshd)"
New-NetFirewallRule -DisplayName "SSH Server (sshd)" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 22 `
  -RemoteAddress 192.168.20.0/24
```

## Post-Setup: Using SSH with Ansible

### Basic SSH Connection Test
```bash
ansible -i ansible/inventory/hosts.yml spraycheese -m ping -u james
```

### Running Playbooks via SSH
```bash
# Now you can run playbooks using SSH instead of WinRM
cd ansible
ansible-playbook playbooks/platform/deploy-ollama.yml --limit spraycheese

# Note: The ollama playbook currently uses win_* modules which require WinRM.
# You may need to override ansible_connection for some playbooks that still use win_* modules.
```

## See Also

- [OpenSSH for Windows Documentation](https://docs.microsoft.com/en-us/windows-server/administration/openssh/openssh_overview)
- [WinRM Documentation](https://docs.microsoft.com/en-us/windows/win32/winrm/installation-and-configuration-for-windows-remote-management)
- [Ansible Windows Setup](https://docs.ansible.com/ansible/latest/user_guide/windows_setup.html)
