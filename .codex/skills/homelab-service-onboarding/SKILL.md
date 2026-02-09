---
name: homelab-service-onboarding
description: Use this skill when adding a new service to this homelab repo and you need end-to-end Ansible deployment, Technitium DNS records, and Nginx Proxy Manager proxy config that uses the klsll.com wildcard certificate.
---

# Homelab Service Onboarding

Use this skill for new services that must be deployed via Ansible and exposed through NPM + Technitium DNS.

## Outcomes

Produce all of these in one change set:
- Service deployment playbook in `ansible/playbooks/<group>/deploy-<service>.yml`
- Optional role at `ansible/roles/<service>/` when deployment is more than a few tasks
- NPM service definition in `ansible/files/npm/services/<service>.yml`
- Proxy sync playbook in `ansible/playbooks/services/update-<service>-proxy.yml`
- Service documentation page in `docs/services/<service>.md`
- Docs index updates in `README.md`, `docs/README.md`, and `ansible/playbooks/README.md` when playbooks/docs are added

## Required standards

- Run from a feature branch, never `main`.
- Be explicit about service placement (Unraid, platform VM, DNS LXC, GPU worker).
- Use Ansible as source of truth; avoid clickops-only steps.
- Never hardcode secrets; use env vars or 1Password lookups.
- Set timezone to `America/Phoenix` for containers/services that support `TZ`.
- For Unraid targets, prefer `raw`/shell-safe commands because Python may be unavailable.
- Use stable/pinned image tags for critical services (avoid `latest` unless justified).
- Include health checks with retries and clear failure messages.

## Proxy and DNS standards (mandatory)

- Every externally exposed app must have an NPM proxy host entry.
- Every new proxy host must use `certificate: klsll-wildcard`.
- Proxy defaults:
  - `ssl_forced: true`
  - `hsts: true`
  - `http2: true`
  - `scheme: http` unless upstream requires https
- Add DNS A records in the same `<service>.yml` under `dns_records`.
- For services proxied through NPM, point DNS record value to NPM IP (`192.168.20.50`) unless there is a documented exception.
- Include `ansible/files/npm/services/certificates.yml` in `npm_proxy_config_paths` unless the playbook intentionally uses a pre-existing cert map path and documents why.

## Implementation workflow

1. Pick target host group and deployment style.
2. Create/extend deployment playbook:
   - For simple deployment, direct playbook tasks are acceptable.
   - For reusable deployment, create a role and keep playbook thin.
3. Create NPM+DNS service file from `references/npm-service-template.yml`.
4. Create proxy sync playbook from `references/update-proxy-playbook-template.yml`.
5. Update documentation:
   - Add `docs/services/<service>.md` with deploy/run/verify/rollback.
   - Add links in `README.md` and `docs/README.md`.
   - Update `ansible/playbooks/README.md` if playbooks were added.
   - Prepare Notion update content from `references/notion-update-template.md`.
6. Validate and run in order:
   - `cd ansible`
   - `ansible-playbook playbooks/<group>/deploy-<service>.yml --syntax-check`
   - `ansible-playbook playbooks/<group>/deploy-<service>.yml --check --diff --limit <host>`
   - `ansible-playbook playbooks/<group>/deploy-<service>.yml --diff --limit <host> -v`
   - `ansible-playbook playbooks/services/update-<service>-proxy.yml --syntax-check`
   - `ansible-playbook playbooks/services/update-<service>-proxy.yml --check --diff --limit unraid`
   - `ansible-playbook playbooks/services/update-<service>-proxy.yml --diff --limit unraid -v`
7. Verify endpoint and DNS resolution after deploy.

## Additional standards this skill should enforce

- Idempotence gate: rerun both deploy and proxy playbooks in `--check --diff` and expect no unintended changes.
- Required-variable gate: fail fast when required env vars are missing (use `assert` with actionable messages).
- Network gate: ensure required Docker network exists (or fail with explicit remediation).
- Security gate: no plaintext secrets in repo; placeholders must use `CHANGEME_*` naming.
- Observability gate: include at least one post-deploy health check and one log inspection command in task output/docs.
- Rollback gate: provide exact rollback command(s), usually `docker compose down` or redeploy prior pinned image tag.
- Naming gate: enforce predictable filenames (`deploy-<service>.yml`, `update-<service>-proxy.yml`, `<service>.yml`).
- Documentation gate: PR is incomplete unless README/docs/service docs and Notion content are updated.

## References

- Service deployment playbook scaffold: `references/deploy-playbook-template.yml`
- NPM + DNS service definition scaffold: `references/npm-service-template.yml`
- Proxy sync playbook scaffold: `references/update-proxy-playbook-template.yml`
- Notion update scaffold: `references/notion-update-template.md`
