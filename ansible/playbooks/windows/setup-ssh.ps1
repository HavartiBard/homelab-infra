# =============================================================================
# Setup SSH on Windows - PowerShell Script
# =============================================================================
# This script sets up OpenSSH Server on Windows for key-based authentication.
#
# USAGE:
# 1. Save this script as setup-ssh.ps1
# 2. Copy your SSH public key to C:\temp\id_ed25519_homelab.pub (or modify path below)
# 3. Open PowerShell as Administrator
# 4. Run: Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
# 5. Run: .\setup-ssh.ps1
#
# =============================================================================

param(
    [string]$SSHUser = "james",
    [string]$SSHPort = "22",
    [string]$PublicKeyPath = "C:\temp\id_ed25519_homelab.pub"
)

# Color functions for output
function Write-Success {
    Write-Host "✅ $args" -ForegroundColor Green
}

function Write-Info {
    Write-Host "ℹ️  $args" -ForegroundColor Cyan
}

function Write-Warning {
    Write-Host "⚠️  $args" -ForegroundColor Yellow
}

function Write-Error {
    Write-Host "❌ $args" -ForegroundColor Red
}

# Check if running as Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator!"
    exit 1
}

Write-Info "Starting OpenSSH Server setup..."
Write-Info "SSH User: $SSHUser"
Write-Info "SSH Port: $SSHPort"
Write-Info "Public Key: $PublicKeyPath"
Write-Host ""

# =============================================================================
# Step 1: Check if OpenSSH Server is installed
# =============================================================================
Write-Info "Step 1: Checking OpenSSH Server installation..."

$service = Get-Service sshd -ErrorAction SilentlyContinue
if ($service) {
    Write-Success "OpenSSH Server is already installed"
} else {
    Write-Info "Installing OpenSSH Server..."
    try {
        Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 -ErrorAction Stop | Out-Null
        Write-Success "OpenSSH Server installed successfully"
    } catch {
        Write-Error "Failed to install OpenSSH Server: $_"
        Write-Info "Note: You may need to install it manually via Settings (Apps - Optional Features)"
        exit 1
    }
}

Write-Host ""

# =============================================================================
# Step 2: Start and enable SSH service
# =============================================================================
Write-Info "Step 2: Starting and enabling SSH service..."

try {
    Start-Service sshd -ErrorAction Stop
    Write-Success "sshd service started"
} catch {
    Write-Warning "Could not start sshd: $_"
}

try {
    Set-Service -Name sshd -StartupType 'Automatic' -ErrorAction Stop
    Write-Success "sshd set to auto-start"
} catch {
    Write-Warning "Could not set auto-start: $_"
}

Write-Host ""

# =============================================================================
# Step 3: Create .ssh directory
# =============================================================================
Write-Info "Step 3: Creating .ssh directory..."

$sshDir = "C:\Users\$SSHUser\.ssh"
try {
    if (-not (Test-Path $sshDir)) {
        New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
        Write-Success ".ssh directory created at $sshDir"
    } else {
        Write-Success ".ssh directory already exists"
    }
} catch {
    Write-Error "Failed to create .ssh directory: $_"
    exit 1
}

Write-Host ""

# =============================================================================
# Step 4: Copy SSH public key to authorized_keys
# =============================================================================
Write-Info "Step 4: Installing SSH public key..."

$authKeysFile = "$sshDir\authorized_keys"

# Check if public key file exists
if (-not (Test-Path $PublicKeyPath)) {
    Write-Error "Public key not found at: $PublicKeyPath"
    Write-Info "Please copy your SSH public key to: $PublicKeyPath"
    Write-Info ""
    Write-Info "From your Linux control machine, run:"
    Write-Info "  scp ~/.ssh/id_ed25519_homelab.pub james@192.168.20.50:C:\temp\"
    Write-Info ""
    exit 1
}

try {
    # Read the public key
    $pubkey = Get-Content $PublicKeyPath -Raw

    # Add to authorized_keys if it doesn't already exist
    if (-not (Test-Path $authKeysFile)) {
        $pubkey | Out-File -FilePath $authKeysFile -Encoding ASCII -NoNewline
        Write-Success "Public key installed to authorized_keys"
    } else {
        $existingKeys = Get-Content $authKeysFile -Raw
        if ($existingKeys -notmatch [regex]::Escape($pubkey.Trim())) {
            Add-Content -Path $authKeysFile -Value $pubkey -Encoding ASCII
            Write-Success "Public key added to authorized_keys"
        } else {
            Write-Success "Public key already in authorized_keys"
        }
    }
} catch {
    Write-Error "Failed to install public key: $_"
    exit 1
}

Write-Host ""

# =============================================================================
# Step 5: Set correct permissions
# =============================================================================
Write-Info "Step 5: Setting file permissions..."

try {
    # Set permissions on .ssh directory
    $acl = Get-Acl $sshDir
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "$env:COMPUTERNAME\$SSHUser",
        "FullControl",
        "ContainerInherit,ObjectInherit",
        "None",
        "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl -Path $sshDir -AclObject $acl
    Write-Success ".ssh directory permissions set"

    # Set permissions on authorized_keys file
    $acl = Get-Acl $authKeysFile
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "$env:COMPUTERNAME\$SSHUser",
        "FullControl",
        "None",
        "None",
        "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl -Path $authKeysFile -AclObject $acl
    Write-Success "authorized_keys permissions set"
} catch {
    Write-Error "Failed to set permissions: $_"
    exit 1
}

Write-Host ""

# =============================================================================
# Step 6: Configure sshd_config
# =============================================================================
Write-Info "Step 6: Configuring sshd_config..."

$sshdConfigPath = "C:\ProgramData\ssh\sshd_config"

try {
    # Backup original config
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item $sshdConfigPath "$sshdConfigPath.bak.$timestamp" -Force
    Write-Success "Original sshd_config backed up"

    # Read config
    $config = Get-Content $sshdConfigPath -Raw

    # Enable public key authentication
    $config = $config -replace '(?m)^#?\s*PubkeyAuthentication\s+.*$', 'PubkeyAuthentication yes'

    # Disable password authentication
    $config = $config -replace '(?m)^#?\s*PasswordAuthentication\s+.*$', 'PasswordAuthentication no'

    # Disable empty passwords
    $config = $config -replace '(?m)^#?\s*PermitEmptyPasswords\s+.*$', 'PermitEmptyPasswords no'

    # Add AuthorizedKeysFile if not present
    if ($config -notmatch 'AuthorizedKeysFile') {
        $config += "`n`n# Use public key authentication`nAuthorizedKeysFile .ssh/authorized_keys`n"
    }

    # Write config back
    Set-Content $sshdConfigPath -Value $config -Encoding UTF8
    Write-Success "sshd_config updated"
} catch {
    Write-Error "Failed to configure sshd_config: $_"
    exit 1
}

Write-Host ""

# =============================================================================
# Step 7: Validate sshd_config syntax
# =============================================================================
Write-Info "Step 7: Validating sshd_config..."

try {
    $sshPath = "C:\Program Files\OpenSSH-Win64\sshd.exe"
    if (Test-Path $sshPath) {
        $result = & $sshPath -T 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "sshd_config syntax is valid"
        } else {
            Write-Warning "sshd_config validation returned: $result"
        }
    } else {
        Write-Warning "Could not find sshd.exe at expected location, skipping validation"
    }
} catch {
    Write-Warning "Could not validate sshd_config: $_"
}

Write-Host ""

# =============================================================================
# Step 8: Restart SSH service
# =============================================================================
Write-Info "Step 8: Restarting SSH service..."

try {
    Restart-Service sshd -Force
    Write-Success "sshd service restarted"
    Start-Sleep -Seconds 2
} catch {
    Write-Error "Failed to restart sshd: $_"
    exit 1
}

Write-Host ""

# =============================================================================
# Step 9: Create Windows Firewall rule
# =============================================================================
Write-Info "Step 9: Configuring Windows Firewall..."

try {
    $rule = Get-NetFirewallRule -DisplayName "SSH Server (sshd)" -ErrorAction SilentlyContinue
    if ($rule) {
        Write-Success "Firewall rule already exists"
    } else {
        New-NetFirewallRule -DisplayName "SSH Server (sshd)" `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort $SSHPort `
            -ErrorAction Stop | Out-Null
        Write-Success "Firewall rule created for port $SSHPort"
    }
} catch {
    Write-Warning "Could not create firewall rule: $_"
    Write-Info "You may need to create the rule manually"
}

Write-Host ""

# =============================================================================
# Step 10: Verify SSH is listening
# =============================================================================
Write-Info "Step 10: Verifying SSH is listening..."

$retries = 5
$listening = $false

for ($i = 1; $i -le $retries; $i++) {
    try {
        $connection = Get-NetTCPConnection -LocalPort $SSHPort -State Listen -ErrorAction SilentlyContinue
        if ($connection) {
            Write-Success "SSH is listening on port $SSHPort"
            $listening = $true
            break
        }
    } catch {
        # Ignore errors
    }

    if ($i -lt $retries) {
        Write-Info "Attempt $i of $retries : Waiting for SSH to start..."
        Start-Sleep -Seconds 2
    }
}

if (-not $listening) {
    Write-Warning "SSH does not appear to be listening on port $SSHPort"
    Write-Info "Check service status with: Get-Service sshd"
}

Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Success "SSH Setup Complete!"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Info "SSH is now enabled on this Windows system"
Write-Host ""
Write-Host "Connect from your control machine with:" -ForegroundColor Cyan
Write-Host "  ssh -i ~/.ssh/id_ed25519_homelab $SSHUser@192.168.20.50" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or test with Ansible:" -ForegroundColor Cyan
Write-Host "  ansible -i inventory/hosts.yml -u $SSHUser spraycheese -m ping" -ForegroundColor Yellow
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
Get-Service sshd | Select-Object @{Name='Name';Expression={$_.Name}}, @{Name='Status';Expression={$_.Status}}, @{Name='StartType';Expression={$_.StartType}} | Format-Table -AutoSize
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
