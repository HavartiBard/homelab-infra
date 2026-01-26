# Gitea Runners - Quick Start Guide

## 🚀 Deploy in 5 Minutes

### 1. Generate Runner Token
```
1. Visit: https://gitea.klsll.com/admin/runners
2. Click "Create New Runner"
3. Copy the registration token
```

### 2. Deploy Runners
```bash
cd ansible

# Option A: Using script (recommended)
./scripts/deploy-gitea-runners.sh --token YOUR_TOKEN_HERE

# Option B: Direct ansible-playbook
export GITEA_RUNNER_TOKEN="YOUR_TOKEN_HERE"
ansible-playbook playbooks/platform/deploy-gitea-runners.yml
```

### 3. Verify
```
https://gitea.klsll.com/admin/runners
→ Should show 2 runners in "online" state
```

## 📊 Common Commands

| Task | Command |
|------|---------|
| **Deploy 2 runners** | `./scripts/deploy-gitea-runners.sh --token TOKEN` |
| **Deploy 4 runners** | `./scripts/deploy-gitea-runners.sh --token TOKEN --count 4` |
| **More memory** | `./scripts/deploy-gitea-runners.sh --token TOKEN --memory 8g` |
| **Dry run** | `./scripts/deploy-gitea-runners.sh --token TOKEN --dry-run` |
| **View logs** | `ssh root@192.168.20.14` → `cd /mnt/user/appdata/gitea-runner/stacks && docker compose logs -f` |
| **Restart runners** | `cd /mnt/user/appdata/gitea-runner/stacks && docker compose restart` |
| **Add more runners** | Re-run script with higher `--count` |

## ✅ Test It Works

### Create a simple workflow
In any repository, create `.gitea/workflows/test.yml`:

```yaml
name: Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Hello from Gitea Runner!"
```

Push to trigger the workflow. You should see it run in the Actions tab.

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Runners show "offline" | Token expired (1hr validity). Generate new token and redeploy. |
| Jobs fail to start | Check logs: `docker logs gitea-runner-1` |
| High memory usage | Reduce runner count or increase memory limit |
| Image push fails | Verify registry credentials in role defaults |

## 📚 Full Documentation

See `docs/GITEA_RUNNERS.md` for:
- Advanced configuration
- Multi-host deployment
- Scaling strategies
- Complete troubleshooting guide
- Security considerations

## 🎯 Key Paths

| Path | Purpose |
|------|---------|
| `ansible/playbooks/platform/deploy-gitea-runners.yml` | Main deployment playbook |
| `ansible/roles/gitea-runner/` | Role with templates & tasks |
| `/mnt/user/appdata/gitea-runner/` | Runner data on Unraid |
| `https://gitea.klsll.com/admin/runners` | Gitea runner management UI |

## 🆘 Need Help?

1. **Check syntax**: `ansible-playbook playbooks/platform/deploy-gitea-runners.yml --syntax-check`
2. **Dry run**: Add `--check --diff` to playbook command
3. **SSH to Unraid**: `ssh root@192.168.20.14` (IP from inventory)
4. **View detailed logs**: `docker compose logs --tail 100 gitea-runner-1`
