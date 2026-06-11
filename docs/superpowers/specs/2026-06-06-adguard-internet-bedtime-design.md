# AdGuard "Internet Bedtime" for `user_child` Clients — Design

- **Date:** 2026-06-06
- **Status:** Approved (design)
- **Branch:** `feature/adguard-internet-bedtime`
- **Owner:** James

## Goal

Block **all internet (DNS)** for a subset of devices during a nightly window
(**01:00–08:00 `America/Phoenix`**), targeting devices by the AdGuard built-in
client tag `user_child`. The block must be fully managed by the existing
`adguard` Ansible role (no clickops) and replicate from agh1 to agh2.

## Scope & constraints

- **Enforcement layer: AdGuard DNS only.** This is a DNS-layer block. A device
  using hardcoded DNS, encrypted DNS (DoH/DoT), or a VPN can bypass it. This is
  acceptable for the target devices (kids' phones/tablets/PCs/TV on
  DHCP-assigned DNS). A true unbypassable block would require router/firewall
  rules and is explicitly out of scope.
- **Targeting: client tags.** Uses AdGuard's `$ctag` modifier. The single rule
  `*$ctag=user_child` blocks every domain for any client tagged `user_child`.
  `ctag` is AdGuard-Home-only and `user_child` is a built-in "By user group" tag.
- **Schedule: every night, 01:00–08:00 `America/Phoenix`**, all 7 days.
- **No native AdGuard scheduler is used.** AdGuard's only native scheduling is
  the blocked-services *schedule*, which (a) only covers the curated service
  registry — not "all internet" — and (b) defines a *pause* window, which is the
  wrong semantics. We therefore use an external reconciler + the REST API.

## Architecture

```
systemd timer (agh1 host, every ~10 min)
   └─ /opt/adguard/bedtime-block.py
        ├─ GET  http://127.0.0.1:3000/control/filtering/status   (read user_rules)
        └─ POST http://127.0.0.1:3000/control/filtering/set_rules (write merged rules)
                                   │
                          adguardhome-sync (*/5 min, agh1 → agh2)
                                   ▼
                            agh2 (192.168.20.5)
```

### Why agh1 only (single writer)

`adguardhome-sync` runs every 5 minutes and replicates client settings **and**
filters/user-rules from the origin (agh1, `192.168.20.4`) to the replica (agh2,
`192.168.20.5`). The reconciler therefore writes **only to agh1**; sync fans the
change out to agh2 within ≤5 min. Running the reconciler on agh2 as well would
fight the sync loop (agh1 would overwrite agh2 on the next cycle). The
`adguardhome-sync` `filters` feature syncs filter lists and user rules together,
so user rules cannot be excluded from sync independently — single-writer-on-agh1
is the clean choice.

### Accepted failure mode

If agh1 is fully down, agh2 keeps serving its last-synced state and won't toggle
until agh1 returns. For an overnight device block this is acceptable (worst case:
the block fails to engage or lift on time on the secondary while the primary is
offline).

## Components

### 1. Reconciler script — `templates/bedtime-block.py.j2`

Python 3 stdlib only (agh1 runs Python 3.12). Responsibilities:

1. Determine **desired state**: is "now" (in `adguard_bedtime_timezone`) within
   `[adguard_bedtime_start, adguard_bedtime_end)`? A `--now HH:MM` flag overrides
   "now" for testing.
2. GET current user rules from `/control/filtering/status`.
3. Strip any existing managed block delimited by marker lines:
   - `! BEGIN bedtime-block`
   - `*$ctag=user_child`
   - `! END bedtime-block`
4. If in-window, re-insert the managed block.
5. POST the merged rule list to `/control/filtering/set_rules`
   (body: `{"rules": [...]}`). Skip the POST if the rule list is unchanged
   (idempotent — avoids needless writes/log churn).

**Idempotent & marker-delimited:** the script only ever touches its own marked
block, so it coexists with any other user rules (Ansible-managed or manual) and
self-heals if an Ansible redeploy transiently clears `user_rules`.

Auth: HTTP Basic, credentials read from a root-only env file (below).
Exit non-zero on API errors so the systemd unit surfaces failures to the journal.

### 2. Credentials file — `templates/bedtime-block.env.j2`

Mode `0600`, owner root. Contents:

```
ADGUARD_URL=http://127.0.0.1:{{ adguard_http_port }}
ADGUARD_USER={{ adguard_admin_user }}
ADGUARD_PASS={{ adguard_admin_password }}
```

Backed by existing vault vars (`vault_adguard_admin_username`,
`vault_adguard_admin_password`). `no_log: true` on the deploying task.

### 3. systemd units — `templates/adguard-bedtime.service.j2` + `.timer.j2`

- `adguard-bedtime.service`: `Type=oneshot`,
  `EnvironmentFile=/opt/adguard/bedtime-block.env`,
  `ExecStart=/usr/bin/python3 /opt/adguard/bedtime-block.py`.
- `adguard-bedtime.timer`: `OnCalendar=*:0/{{ adguard_bedtime_interval_min }}`
  (every 10 min), `Persistent=true`, `OnBootSec=2min`.

Both deployed and `enabled --now` **only on the sync origin** and only when the
feature is enabled:
`when: adguard_bedtime_enabled and ansible_host == adguard_sync_origin`.
When `adguard_bedtime_enabled` is false, the timer is `disabled --now` and the
managed rule block is cleared on the final run.

### 4. Persistent clients in the template — `templates/AdGuardHome.yaml.j2`

Replace the hardcoded `clients.persistent: []` with a render of
`adguard_persistent_clients`. This fixes a **latent footgun**: today every
`deploy-adguard-config.yml` run wipes all UI-created clients (and their tags).

Per-client rendered fields (all current clients use global settings, so their
per-client safe_search/filtering toggles are inert and intentionally omitted):

```yaml
clients:
  runtime_sources: { ... unchanged ... }
  persistent:
{% for c in adguard_persistent_clients %}
    - name: "{{ c.name }}"
      ids:
{% for id in c.ids %}
        - "{{ id }}"
{% endfor %}
      tags:
{% for t in c.tags %}
        - {{ t }}
{% endfor %}
      use_global_settings: true
      use_global_blocked_services: true
      blocked_services:
        schedule:
          time_zone: {{ adguard_bedtime_timezone }}
{% endfor %}
```

Also: change the global `filtering.blocked_services.schedule.time_zone` from
`America/Los_Angeles` to `{{ adguard_bedtime_timezone }}` (`America/Phoenix`),
aligning with the repo timezone convention.

### 5. Variables

`ansible/roles/adguard/defaults/main.yml` (feature defaults):

```yaml
adguard_bedtime_enabled: true
adguard_bedtime_ctag: user_child
adguard_bedtime_start: "01:00"
adguard_bedtime_end: "08:00"
adguard_bedtime_timezone: America/Phoenix
adguard_bedtime_interval_min: 10
```

`ansible/group_vars/agh/main.yml` (device inventory — environment data):
seeded one-time from the live agh1 export.

```yaml
adguard_persistent_clients:
  - { name: "Cheddar",        ids: ["192.168.1.81"],  tags: ["device_laptop"] }
  - { name: "Dev VM",         ids: ["192.168.20.60"], tags: [] }
  - { name: "Emma PC",        ids: ["192.168.1.55"],  tags: ["device_pc", "os_windows", "user_child"] }
  - { name: "Emma TV",        ids: ["192.168.1.61"],  tags: ["device_tv", "user_child"] }
  - { name: "James Iphone",   ids: ["192.168.1.15"],  tags: ["device_phone", "user_admin"] }
  - { name: "Jen Iphone",     ids: ["192.168.1.25"],  tags: [] }
  - { name: "Madison IPAD",   ids: ["192.168.1.75"],  tags: ["device_tablet", "user_child"] }
  - { name: "Parker PC",      ids: ["192.168.1.57"],  tags: ["device_pc", "os_windows", "user_child"] }
  - { name: "Someones Phone", ids: ["192.168.1.83"],  tags: [] }
```

Devices currently in the bedtime group (tagged `user_child`): **Emma PC,
Emma TV, Madison IPAD, Parker PC**.

### 6. Tasks — `tasks/main.yml` additions

- Deploy `bedtime-block.py`, `bedtime-block.env` (0600), and the two systemd
  units (sync-origin only).
- `systemctl daemon-reload` + `enable --now` the timer when enabled; `disable
  --now` when disabled.
- Order after the existing AdGuard-config deploy so the container is up.

## Operational notes

### Clients UI becomes read-only

After this change, AdGuard's *Clients* UI is effectively read-only: new/changed
clients must be added to `group_vars/agh/main.yml` or they are reverted on the
next deploy. To re-import after a bulk UI edit:

```bash
curl -s -u "$AGH_USER:$AGH_PASS" "http://192.168.20.4:3000/control/clients" \
  | python3 -c 'import sys, yaml, json; \
clients = json.load(sys.stdin)["clients"]; \
print(yaml.safe_dump({"adguard_persistent_clients": [\
  {"name": c["name"], "ids": c["ids"], "tags": c["tags"]} for c in clients]}, sort_keys=False))'
```

### Disable the feature

- Permanent/IaC: set `adguard_bedtime_enabled: false`, redeploy (timer removed,
  rule cleared on final run).
- Immediate/manual: `systemctl disable --now adguard-bedtime.timer` on agh1,
  then run `python3 /opt/adguard/bedtime-block.py` once to clear the rule.

## Verification

1. **Timer scheduled:** `systemctl list-timers adguard-bedtime.timer` on agh1.
2. **In-window behavior:** `python3 /opt/adguard/bedtime-block.py --now 01:30`
   then confirm `*$ctag=user_child` is present in
   `/control/filtering/status` (`user_rules`).
3. **Out-of-window behavior:** `python3 /opt/adguard/bedtime-block.py --now 12:00`
   then confirm the rule is absent.
4. **End-to-end:** from a `user_child`-tagged device during the window,
   `nslookup example.com` returns a blocked response (NXDOMAIN / 0.0.0.0).
5. **Replication:** within ≤5 min, the rule appears on agh2
   (`curl .../control/filtering/status` against 192.168.20.5).
6. **Idempotence:** re-run `deploy-adguard-config.yml --check` → `changed=0`.

## Rollback

- Revert the branch / PR.
- Or set `adguard_bedtime_enabled: false` and redeploy.
- The persistent-clients seed matches the current live state, so deploying the
  template change alone does not alter existing client config.

## Out of scope / future

- Router/firewall hard block for bypass-resistant enforcement.
- Per-tag or per-day differentiated schedules (e.g. school nights vs weekends).
- A second tag/window (e.g. `user_regular` with a different curfew).
```
