# Gitea Authentication & Integration Guide for AI Agents (Claude Code, Codex)

This guide explains how AI agents authenticate with your Gitea instance and what operations are supported.

## Authentication Method: SSH Key-Based Git Operations

### How It Works

AI agents authenticate to Gitea using **SSH key-based authentication**, not passwords or API tokens. This is the most secure and reliable method for automated git operations.

**Key Components:**
- **SSH Key Location**: `~/.ssh/id_ed25519_homelab` (private key)
- **Gitea Instance**: `gitea.klsll.com` (requires SSH on port 22)
- **Git Remote**: `ssh://git@gitea.klsll.com/Homelab/homelab-infra.git`
- **Authentication Type**: Ed25519 elliptic curve cryptography

### SSH Key Details

```bash
# Key info
File: ~/.ssh/id_ed25519_homelab
Type: ED25519 (more secure than RSA)
Usage: SSH-based git operations only
Scope: Can be used for any Gitea operation the user has permission for
```

**Key is already configured in:**
- `~/.ssh/config` (implicit, via standard SSH setup)
- `~/.ssh/id_ed25519_homelab.pub` (public key on Gitea server)

### Testing Authentication

Any agent can verify Gitea connectivity:

```bash
# Test SSH access (shows branch list)
git ls-remote ssh://git@gitea.klsll.com/Homelab/homelab-infra.git

# Example output:
# 0bc57898a0bfb2ba29ce79bbe258249181a7c430	HEAD
# 0bc57898a0bfb2ba29ce79bbe258249181a7c430	refs/heads/feature/homepage-dashboard-v2
# cf6c4f3d47b9f5231c04c1ac0daa660aee2b6301	refs/heads/main
```

## Current Repository Setup

### Git Remote Configuration

```bash
# Current remote
origin → ssh://git@gitea.klsll.com/Homelab/homelab-infra.git

# This maps to:
# Organization: Homelab
# Repository: homelab-infra
# Access: SSH via git@gitea.klsll.com
```

### Repository Structure

```
homelab-infra/
├── ansible/          # Deployment automation
│   ├── roles/       # Reusable Ansible roles
│   ├── playbooks/   # Deployment playbooks
│   ├── files/       # Configuration templates
│   └── inventory/   # Host definitions
├── stacks/          # Docker Compose reference stacks
├── docker/          # Custom Dockerfiles
├── docs/            # Documentation
└── .gitignore       # Files not tracked (secrets, caches, etc.)
```

## What AI Agents Can Do (✅ Supported)

### 1. **Clone Repository**
```bash
git clone ssh://git@gitea.klsll.com/Homelab/homelab-infra.git
```
- Full read access to all committed files
- Access to all branches and history
- Authentication happens automatically via SSH key

### 2. **Read Git History & Status**
```bash
git log --oneline -10              # View recent commits
git status                         # Current branch status
git diff                          # See uncommitted changes
git show <commit>                 # View specific commit
git branch -a                     # List all branches
git ls-remote origin              # List remote branches
```

### 3. **Commit Changes**
```bash
git add <files>
git commit -m "Commit message"
```
- Full commit capabilities
- Can create meaningful commit messages
- Should follow repository conventions (see `.commitlintrc` if present)

### 4. **Push Changes**
```bash
git push origin <branch>           # Push to current branch
git push origin HEAD:refs/heads/<branch>  # Push to specific branch
```
- Can push to any branch the user has access to
- **Note**: Force push (`git push --force`) should be avoided unless explicitly requested
- SSH authentication handles authorization automatically

### 5. **Create & Switch Branches**
```bash
git checkout -b feature/new-feature
git push origin feature/new-feature -u
```
- Can create feature branches
- Can push new branches
- Useful for organizing work

### 6. **Merge Operations** (via Gitea UI or git commands)
```bash
git merge <branch>
git push origin main
```
- Can merge branches locally
- Gitea web UI preferred for pull requests/code review
- SSH authentication enables this

### 7. **File Operations**
```bash
# Create/edit/delete files with proper git tracking
git add <file>
git commit -m "message"
git push
```

### 8. **Access Gitea API** (Limited, requires token)
```bash
# Some Gitea API endpoints require authentication tokens
# SSH key does NOT authenticate API calls
# Would need separate personal access token for full API access
curl -H "Authorization: token <GITEA_TOKEN>" \
  https://gitea.klsll.com/api/v1/repos/Homelab/homelab-infra
```

## What AI Agents CANNOT Do (❌ Not Supported)

### 1. **Direct Gitea API Access (without token)**
- SSH keys authenticate **git operations only**, not HTTP API calls
- Would need a personal access token in Gitea for API access
- Examples that won't work without token:
  - Fetching action run logs
  - Creating pull requests via API
  - Viewing runner status
  - Reading commit comments

### 2. **Web UI Operations**
- Cannot click buttons or navigate Gitea web interface
- Cannot create pull requests through UI
- Cannot manage repositories, users, or settings
- Cannot view action/workflow results directly from API

### 3. **SSH Command Execution**
- Cannot SSH into Gitea server itself
- Can only use `git` commands over SSH
- No shell access to `git@gitea.klsll.com`

### 4. **Gitea-Specific Workflows**
- Cannot auto-generate pull requests
- Cannot trigger webhooks
- Cannot modify repository settings
- Cannot create or delete branches remotely (only via git push)

## Best Practices for AI Agents

### ✅ Do:

1. **Use SSH for all git operations**
   ```bash
   git clone ssh://git@gitea.klsll.com/...
   ```
   Not: `git clone https://gitea.klsll.com/...` (requires separate auth)

2. **Test authentication before operations**
   ```bash
   git ls-remote origin  # Quick test, no side effects
   ```

3. **Write meaningful commit messages**
   - First line: short summary (50 chars)
   - Blank line
   - Detailed explanation if needed
   - Sign with: `Co-Authored-By: <Agent Name> <noreply@example.com>`

4. **Use feature branches for isolated work**
   ```bash
   git checkout -b feature/descriptive-name
   # Make changes
   git push origin feature/descriptive-name -u
   ```

5. **Verify changes before pushing**
   ```bash
   git diff              # Review changes
   git status            # Check what's staged
   git diff --cached     # See staged changes
   ```

6. **Handle SSH key securely**
   - Never hardcode the key path
   - Always use `~/.ssh/id_ed25519_homelab` (standard location)
   - Never attempt to read the private key content
   - SSH agent handles authentication transparently

### ❌ Don't:

1. **Don't use HTTP/HTTPS URLs** (unless password auth is set up)
   - SSH is already configured and working
   - Avoid mixed auth methods

2. **Don't force push without explicit request**
   ```bash
   # BAD:
   git push --force origin main

   # GOOD:
   git push origin main  # Normal push
   ```

3. **Don't hardcode credentials**
   - SSH key is handled automatically
   - Never add API tokens to environment variables
   - Never commit secrets

4. **Don't assume the SSH key exists**
   - Check: `ls -la ~/.ssh/id_ed25519_homelab`
   - If missing, user needs to set it up or provide alternative auth

5. **Don't try to fetch Gitea API data via SSH**
   - API calls require HTTP(S)
   - API authentication requires personal access token
   - Use git commands for git operations, not API

## Gitea Repository Details

### Organization & Access
```
Organization: Homelab
Repository: homelab-infra
Owner: HavartiBard (likely)
Access Level: Full read/write (via SSH key)
Branch Protection: Check main branch settings in Gitea UI
```

### Important Branches

| Branch | Purpose | Push Policy |
|--------|---------|------------|
| `main` | Production/stable code | Typically requires PR review |
| `feature/*` | Feature development | Safe to push without review |
| `feature/homepage-dashboard-v2` | Current working branch | Can push directly |

### Verify Current Setup

```bash
cd /home/james/CascadeProjects/homelab-infra

# Show remote
git remote -v
# Expected output:
# origin    ssh://git@gitea.klsll.com/Homelab/homelab-infra.git (fetch)
# origin    ssh://git@gitea.klsll.com/Homelab/homelab-infra.git (push)

# Show current branch
git branch -vv
# Expected output:
# * feature/homepage-dashboard-v2 0bc5789 Add gitea deployment docs and role

# Show commits ahead of remote
git log origin/feature/homepage-dashboard-v2..HEAD --oneline
```

## Example: Complete Workflow

### Scenario: Make changes and push to feature branch

```bash
# 1. Check current status
git status
git log --oneline -1

# 2. Make changes (create/edit/delete files)
# (AI agent uses Write/Edit/Delete tools)

# 3. Stage changes
git add <modified files>

# 4. Verify before committing
git status                    # See staged files
git diff --cached             # Review staged changes

# 5. Commit with meaningful message
git commit -m "$(cat <<'EOF'
Feature: Add new deployment automation

- Implemented XYZ functionality
- Updated documentation
- Added tests for edge cases

Resolves: #123
Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"

# 6. Push to remote
git push origin feature/homepage-dashboard-v2

# 7. Verify push succeeded
git log -1 --format="%H %s"
git status
```

## Troubleshooting

### Problem: SSH Key Not Found
```
fatal: Could not read from remote repository.
Please make sure you have the correct access rights
and the repository exists.
```

**Solution:**
```bash
# Check key exists
ls -la ~/.ssh/id_ed25519_homelab

# Test SSH connection
ssh -i ~/.ssh/id_ed25519_homelab git@gitea.klsll.com -v

# If key missing, user needs to set it up
```

### Problem: Authentication Fails
```
Permission denied (publickey).
```

**Solution:**
- Verify public key is in Gitea user settings
- Check SSH key permissions: `chmod 600 ~/.ssh/id_ed25519_homelab`
- Verify Gitea server is accessible: `nc -zv gitea.klsll.com 22`

### Problem: Branch Diverged
```
! [rejected] feature/branch -> feature/branch (fetch first)
```

**Solution:**
```bash
git fetch origin
git pull origin feature/branch
git push origin feature/branch
```

### Problem: Cannot Access API
```
{"message":"token is required"}
```

**Solution:**
- This is expected—SSH keys don't authenticate API calls
- Need personal access token for Gitea API
- Use git commands instead of API calls when possible

## Integration with Claude Code

Claude Code can leverage Gitea for:

1. **Read Code**: Access any file in the repository
2. **Make Changes**: Edit/create/delete files
3. **Track Changes**: Use `git diff`, `git status`
4. **Commit**: Create meaningful commits with messages
5. **Push**: Send changes to Gitea
6. **Verify**: Check remote branches and history

### Example: Claude Code Workflow

```
1. User: "Add a new Ansible role for X"
2. Claude Code:
   - Reads existing role structure
   - Creates new files with Write tool
   - Checks git status
   - Commits with git
   - Pushes to feature branch
   - Reports success with git log output
```

## Integration with Codex

Codex can use the same SSH-based authentication to:

1. **Clone the repository**
2. **Read and understand the codebase**
3. **Make changes independently**
4. **Commit and push work**
5. **Coordinate with Claude Code** via git (pull latest, push updates)

### Example: Codex Workflow

```
1. Codex: git clone ssh://git@gitea.klsll.com/Homelab/homelab-infra.git
2. Codex: Analyzes codebase, finds issues
3. Codex: Creates feature branch, makes fixes
4. Codex: git commit -m "Fix: ..."
5. Codex: git push origin feature/fixes
6. Claude Code: Sees changes in git log, can review/iterate
```

### Coordination Strategy

Both agents can work on the same repo:

```bash
# Before starting work
git fetch origin
git pull origin feature/branch

# After making changes
git push origin feature/branch

# View what the other agent did
git log --oneline -10
git show <commit>
```

## Summary

| Capability | Status | Method |
|-----------|--------|--------|
| Clone Repo | ✅ | `git clone ssh://...` |
| Read Files | ✅ | Git or file read tools |
| Commit Changes | ✅ | `git commit` |
| Push to Gitea | ✅ | `git push` (SSH auth) |
| Create Branches | ✅ | `git checkout -b` |
| Merge Branches | ✅ | `git merge` |
| Fetch/Pull | ✅ | `git fetch/pull` |
| Web UI Access | ❌ | Not supported for AI |
| API Access | ⚠️ | Need personal token |
| SSH to Server | ❌ | Not supported |
| Trigger Workflows | ❌ | Not supported directly |

## References

- **Gitea URL**: https://gitea.klsll.com
- **Repository**: https://gitea.klsll.com/Homelab/homelab-infra
- **SSH Format**: `ssh://git@gitea.klsll.com/Homelab/homelab-infra.git`
- **Git Documentation**: https://git-scm.com/doc
- **Gitea Documentation**: https://docs.gitea.com

---

**Last Updated**: 2026-01-27
**Version**: 1.0
**Applicable To**: Claude Code, Codex, any SSH-authenticated AI agent
