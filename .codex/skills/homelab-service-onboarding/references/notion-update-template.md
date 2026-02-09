# Notion Service Catalog Update Template

Use this template when a new service is added or materially changed.

## Service Identity
- Service: `<Service Name>`
- Domain: `<service>.klsll.com`
- Owner: `<Team/Owner>`
- Environment: `homelab`
- Host + IP: `<host>` (`<ip>`)

## Deployment Sources
- Deploy playbook: `ansible/playbooks/<group>/deploy-<service>.yml`
- Proxy playbook: `ansible/playbooks/services/update-<service>-proxy.yml`
- Proxy config: `ansible/files/npm/services/<service>.yml`
- Service docs: `docs/services/<service>.md`

## Networking and TLS
- Upstream: `<ip>:<port>`
- NPM endpoint: `https://<service>.klsll.com`
- Certificate: `klsll-wildcard`
- DNS record target: `192.168.20.50` (unless exception documented)

## Operations
- Verify command(s):
  - `curl -I https://<service>.klsll.com`
  - `<service-specific health check>`
- Rollback command(s):
  - `<docker compose down / playbook rollback command>`

## Change Log Entry
- Change date: `<YYYY-MM-DD>`
- Summary: `<what changed>`
- Risks/notes: `<known caveats or follow-ups>`
