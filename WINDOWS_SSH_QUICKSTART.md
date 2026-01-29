# Windows SSH Setup - Quick Start Guide

**Fastest way to enable SSH on spraycheese without Ansible**

---

## Step 1: Copy Your SSH Public Key to Windows

From your Linux control machine:

```bash
# Copy your SSH public key to spraycheese
scp ~/.ssh/id_ed25519_homelab.pub james@192.168.20.50:C:\temp\
# or if you don't have SSH yet, use a USB drive or other method
```

Or manually:
1. On Linux: Get your public key
   ```bash
   cat ~/.ssh/id_ed25519_homelab.pub
   ```
2. Copy the output
3. On Windows: Save it to `C:\temp\id_ed25519_homelab.pub`

---

## Step 2: Run the PowerShell Setup Script

On Windows (spraycheese):

1. Open **PowerShell as Administrator** (right-click → Run as Administrator)

2. Copy the setup script from the repo:
   ```powershell
   # Download from GitHub or copy from USB
   # Save as: C:\Users\james\setup-ssh.ps1
   ```

   Or create it manually in PowerShell:
   ```powershell
   # Copy the content from: ansible/playbooks/windows/setup-ssh.ps1
   # Paste into notepad, save as C:\Users\james\setup-ssh.ps1
   ```

3. Allow script execution:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   ```

4. Run the script:
   ```powershell
   C:\Users\james\setup-ssh.ps1
   ```

---

## Step 3: Verify SSH is Working

From your Linux control machine:

```bash
# Test SSH connection
ssh -i ~/.ssh/id_ed25519_homelab james@192.168.20.50

# Test with Ansible
cd ansible
ansible -i inventory/hosts.yml -u james spraycheese -m ping
```

---

## What the Script Does

✅ Installs OpenSSH Server
✅ Starts and enables sshd service
✅ Creates .ssh directory and sets permissions
✅ Installs your SSH public key
✅ Configures sshd for key-based auth only
✅ Creates Windows Firewall rule
✅ Validates everything is working

---

## Troubleshooting

### "Public key not found at: C:\temp\id_ed25519_homelab.pub"
**Solution:** Copy your SSH public key to that location first. See Step 1 above.

### "This script must be run as Administrator"
**Solution:** Right-click PowerShell and select "Run as Administrator"

### "cannot be loaded because running scripts is disabled"
**Solution:** Run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

### SSH service won't start
**Solution:** Check if OpenSSH Server is installed:
```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'
```

If not installed, install manually:
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

---

## Manual Alternative (No Script)

If you prefer to set up SSH manually:

```powershell
# Run as Administrator

# 1. Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 2. Start service
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'

# 3. Create .ssh directory
mkdir C:\Users\james\.ssh -Force

# 4. Copy your SSH public key to authorized_keys
# (Use notepad or copy command)
Copy-Item "C:\temp\id_ed25519_homelab.pub" "C:\Users\james\.ssh\authorized_keys"

# 5. Set permissions
icacls "C:\Users\james\.ssh" /inheritance:r /grant:r "${env:COMPUTERNAME}\james:(OI)(CI)F"
icacls "C:\Users\james\.ssh\authorized_keys" /inheritance:r /grant:r "${env:COMPUTERNAME}\james:F"

# 6. Edit C:\ProgramData\ssh\sshd_config with Notepad
notepad C:\ProgramData\ssh\sshd_config
# Set:
#   PubkeyAuthentication yes
#   PasswordAuthentication no
#   PermitEmptyPasswords no

# 7. Restart SSH
Restart-Service sshd

# 8. Verify listening
netstat -an | findstr :22
```

---

## Next Steps

Once SSH is working:

1. **Update Ansible inventory** to use SSH instead of WinRM:
   ```bash
   # Edit ansible/inventory/hosts.yml
   # Change spraycheese to use ansible_connection: ssh
   ```

2. **Run Ansible playbooks** normally:
   ```bash
   cd ansible
   ansible-playbook playbooks/platform/deploy-ollama.yml --limit spraycheese
   ```

3. **Optional: Restrict firewall rule** to specific IPs:
   ```powershell
   # Remove the current rule
   Remove-NetFirewallRule -DisplayName "SSH Server (sshd)"

   # Create a new rule with IP restriction
   New-NetFirewallRule -DisplayName "SSH Server (sshd)" `
     -Direction Inbound `
     -Action Allow `
     -Protocol TCP `
     -LocalPort 22 `
     -RemoteAddress 192.168.20.0/24
   ```

---

## See Also

- `docs/windows-ssh-setup.md` - Full setup guide with WinRM option
- `ansible/playbooks/windows/setup-ssh.yml` - Ansible playbook version
