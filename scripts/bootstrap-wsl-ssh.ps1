<#  bootstrap-wsl-ssh.ps1

Sets up: Windows OpenSSH Server -> ForceCommand into WSL -> WSL user ready for docker
Requires: Run as Administrator
#>

[CmdletBinding()]
param(
  # Windows user used for SSH login (will be forced into WSL)
  [string]$WindowsSshUser = "aiagentwin",

  # WSL distro name as shown by: wsl -l -q  (blank = first distro)
  [string]$WslDistro = "",

  # WSL username to drop into (inside the distro)
  [string]$WslUser = "aiagent",

  # Path to SSH public key to authorize (e.g. C:\temp\win_ai_ed25519.pub)
  [Parameter(Mandatory = $true)]
  [string]$PublicKeyPath,

  # Firewall allow-list. Examples:
  #   "LocalSubnet" (default)
  #   "192.168.1.10,192.168.1.11"
  #   "192.168.1.0/24"
  [string]$AllowedRemoteAddresses = "LocalSubnet",

  # SSH port (keep 22 unless you have a reason)
  [int]$SshPort = 22
)

function Assert-Admin {
  $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if (-not $isAdmin) {
    throw "Run this script in an elevated PowerShell (Run as Administrator)."
  }
}

function Ensure-OpenSSHServer {
  $cap = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*"
  if (-not $cap) { throw "Unable to query Windows capabilities for OpenSSH.Server." }

  if ($cap.State -ne "Installed") {
    Write-Host "Installing OpenSSH Server..."
    Add-WindowsCapability -Online -Name $cap.Name | Out-Null
  } else {
    Write-Host "OpenSSH Server already installed."
  }

  Write-Host "Enabling and starting sshd..."
  Start-Service sshd -ErrorAction SilentlyContinue
  Set-Service -Name sshd -StartupType Automatic

  # Ensure sshd can create firewall rules (optional)
  if (Get-Service ssh-agent -ErrorAction SilentlyContinue) {
    Set-Service -Name ssh-agent -StartupType Manual -ErrorAction SilentlyContinue
  }
}

function Ensure-LocalUserExists {
  $existing = Get-LocalUser -Name $WindowsSshUser -ErrorAction SilentlyContinue
  if ($existing) {
    Write-Host "Windows user '$WindowsSshUser' already exists."
    return
  }

  Write-Host "Creating Windows user '$WindowsSshUser'..."
  $sec = Read-Host "Enter a password for Windows user '$WindowsSshUser' (won't be used for SSH if key-only)" -AsSecureString
  New-LocalUser -Name $WindowsSshUser -Password $sec -PasswordNeverExpires:$true -UserMayNotChangePassword:$true | Out-Null
}

function Ensure-AuthorizedKeys {
  if (-not (Test-Path -Path $PublicKeyPath)) {
    throw "PublicKeyPath not found: $PublicKeyPath"
  }

  $pub = (Get-Content -Raw -Path $PublicKeyPath).Trim()
  if (-not $pub.StartsWith("ssh-")) {
    throw "Public key file doesn't look like an SSH public key: $PublicKeyPath"
  }

  $userProfile = Join-Path "C:\Users" $WindowsSshUser
  if (-not (Test-Path $userProfile)) {
    # Create profile folder if not created yet
    Write-Host "Creating profile folder (may require first login) at $userProfile..."
    New-Item -ItemType Directory -Path $userProfile -Force | Out-Null
  }

  $sshDir = Join-Path $userProfile ".ssh"
  $authKeys = Join-Path $sshDir "authorized_keys"

  New-Item -ItemType Directory -Path $sshDir -Force | Out-Null

  # Append key if not already present
  if (Test-Path $authKeys) {
    $existing = Get-Content -Path $authKeys -ErrorAction SilentlyContinue
    if ($existing -contains $pub) {
      Write-Host "Public key already present in authorized_keys."
    } else {
      Add-Content -Path $authKeys -Value $pub
      Write-Host "Added public key to authorized_keys."
    }
  } else {
    Set-Content -Path $authKeys -Value $pub
    Write-Host "Created authorized_keys and added public key."
  }

  # Set tight ACLs required by Windows OpenSSH
  Write-Host "Setting ACLs on .ssh and authorized_keys..."
  icacls $sshDir /inheritance:r | Out-Null
  icacls $sshDir /grant "${WindowsSshUser}:(OI)(CI)F" | Out-Null
  icacls $sshDir /grant "SYSTEM:(OI)(CI)F" | Out-Null

  icacls $authKeys /inheritance:r | Out-Null
  icacls $authKeys /grant "${WindowsSshUser}:F" | Out-Null
  icacls $authKeys /grant "SYSTEM:F" | Out-Null
}

function Resolve-WslDistro {
  if ($WslDistro -and $WslDistro.Trim().Length -gt 0) { return $WslDistro }

  $distros = & wsl.exe -l -q 2>$null
  if (-not $distros) {
    throw "No WSL distros found. Install WSL and a distro first (e.g., Ubuntu)."
  }

  $first = ($distros | Where-Object { $_ -and $_.Trim().Length -gt 0 } | Select-Object -First 1).Trim()
  if (-not $first) { throw "Could not determine a default WSL distro." }

  Write-Host "WslDistro not provided; using first distro: $first"
  return $first
}

function Ensure-WslUserAndDockerGroup {
  param([string]$DistroName)

  Write-Host "Ensuring WSL user '$WslUser' exists in distro '$DistroName'..."
  # Create user if missing, ensure bash shell
  & wsl.exe -d $DistroName -u root -- bash -lc "id -u '$WslUser' >/dev/null 2>&1 || (useradd -m -s /bin/bash '$WslUser' && echo 'Created user: $WslUser')"

  Write-Host "Ensuring docker group exists and adding '$WslUser' to it..."
  & wsl.exe -d $DistroName -u root -- bash -lc "getent group docker >/dev/null 2>&1 || groupadd docker; usermod -aG docker '$WslUser'"

  # Check docker CLI availability (Docker Desktop WSL integration should provide it)
  $dockerCheck = & wsl.exe -d $DistroName -u $WslUser -- bash -lc "command -v docker >/dev/null 2>&1; echo $?"
  if ($dockerCheck.Trim() -ne "0") {
    Write-Warning "Inside WSL, 'docker' command not found for user '$WslUser'. If you're using Docker Desktop, enable WSL Integration for '$DistroName' in Docker Desktop settings."
  } else {
    Write-Host "Docker CLI is available in WSL for '$WslUser'."
  }
}

function Ensure-ForceCommandWrapper {
  param([string]$DistroName)

  $wrapperPath = "C:\ProgramData\ssh\wsl-shell.cmd"
  $content = @"
@echo off
C:\Windows\System32\wsl.exe -d $DistroName -u $WslUser -- bash -li
"@

  Write-Host "Writing ForceCommand wrapper: $wrapperPath"
  New-Item -ItemType Directory -Path "C:\ProgramData\ssh" -Force | Out-Null
  Set-Content -Path $wrapperPath -Value $content -Encoding ASCII

  return $wrapperPath
}

function Update-SshdConfig {
  param([string]$WrapperPath)

  $cfg = "C:\ProgramData\ssh\sshd_config"
  if (-not (Test-Path $cfg)) {
    throw "sshd_config not found at $cfg. Is OpenSSH Server installed correctly?"
  }

  $text = Get-Content -Raw -Path $cfg

  function SetOrAdd([string]$key, [string]$value) {
    $pattern = "(?m)^[#\s]*$key\s+.*$"
    if ($text -match $pattern) {
      $script:text = [regex]::Replace($text, $pattern, "$key $value")
    } else {
      $script:text = $text.TrimEnd() + "`r`n$key $value`r`n"
    }
  }

  SetOrAdd "PubkeyAuthentication" "yes"
  SetOrAdd "PasswordAuthentication" "no"
  SetOrAdd "PermitEmptyPasswords" "no"

  # Ensure AllowUsers includes our user
  if ($text -match "(?m)^[#\s]*AllowUsers\s+(.*)$") {
    $current = [regex]::Match($text, "(?m)^[#\s]*AllowUsers\s+(.*)$").Groups[1].Value.Trim()
    $users = $current -split "\s+" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
    if ($users -notcontains $WindowsSshUser) {
      $users += $WindowsSshUser
      $text = [regex]::Replace($text, "(?m)^[#\s]*AllowUsers\s+.*$", "AllowUsers " + ($users -join " "))
    } else {
      $text = [regex]::Replace($text, "(?m)^[#\s]*AllowUsers\s+.*$", "AllowUsers " + ($users -join " "))
    }
  } else {
    $text = $text.TrimEnd() + "`r`nAllowUsers $WindowsSshUser`r`n"
  }

  # Remove any existing Match block for this user
  $matchBlockPattern = "(?ms)^Match\s+User\s+$([regex]::Escape($WindowsSshUser))\s*\r?\n(?:^[ \t].*\r?\n)*"
  $text = [regex]::Replace($text, $matchBlockPattern, "")

  # Append our Match block
  $block = @"
Match User $WindowsSshUser
    ForceCommand $WrapperPath
    PermitTTY yes
    AllowTcpForwarding no
    X11Forwarding no
"@

  $text = $text.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
  Set-Content -Path $cfg -Value $text -Encoding ASCII

  Write-Host "Updated sshd_config."
  Restart-Service sshd
  Write-Host "Restarted sshd."
}

function Ensure-FirewallRule {
  $ruleName = "SSH for AI Agents (restricted)"
  $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
  if ($existing) {
    Remove-NetFirewallRule -DisplayName $ruleName | Out-Null
  }

  Write-Host "Creating firewall rule '$ruleName' on port $SshPort allowing: $AllowedRemoteAddresses"
  New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $SshPort `
    -Action Allow `
    -RemoteAddress $AllowedRemoteAddresses | Out-Null
}

# ---------------- main ----------------
try {
  Assert-Admin

  $resolvedDistro = Resolve-WslDistro
  Write-Host "Using WSL distro: $resolvedDistro"
  Write-Host "WSL user: $WslUser"
  Write-Host "Windows SSH user: $WindowsSshUser"
  Write-Host ""

  Ensure-OpenSSHServer
  Ensure-LocalUserExists
  Ensure-AuthorizedKeys
  Ensure-WslUserAndDockerGroup -DistroName $resolvedDistro

  $wrapper = Ensure-ForceCommandWrapper -DistroName $resolvedDistro
  Update-SshdConfig -WrapperPath $wrapper
  Ensure-FirewallRule

  Write-Host ""
  Write-Host "✅ Done."
  Write-Host "Test from another machine:"
  Write-Host "  ssh -i <private_key> $WindowsSshUser@<windows_ip> -p $SshPort"
  Write-Host "You should land directly in WSL and be able to run: docker ps"
} catch {
  Write-Error $_.Exception.Message
  exit 1
}
