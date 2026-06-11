# AdGuard Internet Bedtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block all DNS for AdGuard clients tagged `user_child` nightly from 01:00–08:00 `America/Phoenix`, managed entirely by the `adguard` Ansible role.

**Architecture:** A static Python reconciler runs every 10 min via a systemd timer on agh1 (the sync origin). It decides whether "now" is inside the window and idempotently toggles the rule `*$ctag=user_child` in AdGuard's user rules via the REST API. `adguardhome-sync` (*/5 min) replicates to agh2. Persistent clients (with their tags) move into IaC so deploys stop wiping them.

**Tech Stack:** Ansible, Python 3.12 stdlib (`urllib`, `zoneinfo`, `unittest`), AdGuard Home REST API, systemd timers.

**Design spec:** `docs/superpowers/specs/2026-06-06-adguard-internet-bedtime-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `ansible/roles/adguard/files/bedtime_block.py` | Static reconciler. Pure functions (`is_within_window`, `compute_rules`) + `main()` that talks to the API. Config from env. |
| `ansible/roles/adguard/files/test_bedtime_block.py` | `unittest` tests for the pure logic (no network). |
| `ansible/roles/adguard/templates/bedtime-block.env.j2` | `0600` env file: API URL/creds + window/tag config. |
| `ansible/roles/adguard/templates/adguard-bedtime.service.j2` | oneshot systemd service running the reconciler. |
| `ansible/roles/adguard/templates/adguard-bedtime.timer.j2` | systemd timer firing every `adguard_bedtime_interval_min`. |
| `ansible/roles/adguard/defaults/main.yml` | New `adguard_bedtime_*` feature defaults. |
| `ansible/group_vars/agh/main.yml` | `adguard_persistent_clients` device inventory (seeded from live agh1). |
| `ansible/roles/adguard/templates/AdGuardHome.yaml.j2` | Render `clients.persistent` from the var; fix global `time_zone`. |
| `ansible/roles/adguard/tasks/main.yml` | Deploy script/env/units; enable/disable timer (sync-origin gated). |

---

## Task 1: Reconciler core logic (TDD)

**Files:**
- Create: `ansible/roles/adguard/files/test_bedtime_block.py`
- Create: `ansible/roles/adguard/files/bedtime_block.py`

- [ ] **Step 1: Write the failing tests**

Create `ansible/roles/adguard/files/test_bedtime_block.py`:

```python
import unittest
from datetime import time

import bedtime_block as b


class WindowTests(unittest.TestCase):
    def test_inside_normal_window(self):
        self.assertTrue(b.is_within_window(time(1, 30), time(1, 0), time(8, 0)))

    def test_at_start_is_inside(self):
        self.assertTrue(b.is_within_window(time(1, 0), time(1, 0), time(8, 0)))

    def test_at_end_is_outside(self):
        self.assertFalse(b.is_within_window(time(8, 0), time(1, 0), time(8, 0)))

    def test_midday_outside(self):
        self.assertFalse(b.is_within_window(time(12, 0), time(1, 0), time(8, 0)))

    def test_wrap_before_midnight_inside(self):
        self.assertTrue(b.is_within_window(time(23, 0), time(22, 0), time(6, 0)))

    def test_wrap_after_midnight_inside(self):
        self.assertTrue(b.is_within_window(time(3, 0), time(22, 0), time(6, 0)))

    def test_wrap_midday_outside(self):
        self.assertFalse(b.is_within_window(time(12, 0), time(22, 0), time(6, 0)))


class RuleTests(unittest.TestCase):
    BLOCK = ["! BEGIN bedtime-block", "*$ctag=user_child", "! END bedtime-block"]

    def test_adds_block_when_in_window(self):
        self.assertEqual(b.compute_rules([], True, "user_child"), self.BLOCK)

    def test_no_block_when_out_of_window(self):
        self.assertEqual(b.compute_rules([], False, "user_child"), [])

    def test_preserves_other_rules_in_window(self):
        out = b.compute_rules(["||ads.example.com^"], True, "user_child")
        self.assertEqual(out[0], "||ads.example.com^")
        self.assertIn("*$ctag=user_child", out)

    def test_removes_stale_block_out_of_window(self):
        existing = ["||ads.example.com^"] + self.BLOCK
        self.assertEqual(
            b.compute_rules(existing, False, "user_child"), ["||ads.example.com^"]
        )

    def test_idempotent_in_window(self):
        self.assertEqual(b.compute_rules(self.BLOCK, True, "user_child"), self.BLOCK)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ansible/roles/adguard/files && python3 -m unittest test_bedtime_block -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bedtime_block'`

- [ ] **Step 3: Write the reconciler**

Create `ansible/roles/adguard/files/bedtime_block.py`:

```python
#!/usr/bin/env python3
"""AdGuard "internet bedtime" reconciler.

Idempotently ensures a catch-all block rule for a client tag is present in
AdGuard's user rules during a nightly window, and absent outside it.

Config via environment (see bedtime-block.env):
  ADGUARD_URL, ADGUARD_USER, ADGUARD_PASS
  BEDTIME_START ("01:00"), BEDTIME_END ("08:00"), BEDTIME_TZ, BEDTIME_CTAG

Usage:
  bedtime_block.py                # reconcile using the current time
  bedtime_block.py --now 01:30    # reconcile as if "now" is 01:30 (testing)
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, time
from zoneinfo import ZoneInfo

BEGIN_MARKER = "! BEGIN bedtime-block"
END_MARKER = "! END bedtime-block"


def parse_hhmm(s):
    h, m = s.strip().split(":")
    return time(int(h), int(m))


def is_within_window(now_t, start_t, end_t):
    """True if now_t in [start, end). Handles windows that wrap midnight."""
    if start_t <= end_t:
        return start_t <= now_t < end_t
    return now_t >= start_t or now_t < end_t


def strip_block(rules):
    """Drop the managed marker block (inclusive) from a list of rule lines."""
    out = []
    skipping = False
    for line in rules:
        stripped = line.strip()
        if stripped == BEGIN_MARKER:
            skipping = True
            continue
        if stripped == END_MARKER:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return out


def compute_rules(existing, in_window, ctag):
    """Return the desired user_rules list for the given window state."""
    base = strip_block(existing)
    if not in_window:
        return base
    return base + [BEGIN_MARKER, "*$ctag={}".format(ctag), END_MARKER]


def _request(method, url, user, password, data=None):
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    token = base64.b64encode("{}:{}".format(user, password).encode()).decode()
    headers["Authorization"] = "Basic " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="HH:MM override for testing")
    args = ap.parse_args(argv)

    url = os.environ["ADGUARD_URL"].rstrip("/")
    user = os.environ["ADGUARD_USER"]
    password = os.environ["ADGUARD_PASS"]
    start_t = parse_hhmm(os.environ["BEDTIME_START"])
    end_t = parse_hhmm(os.environ["BEDTIME_END"])
    tz = ZoneInfo(os.environ["BEDTIME_TZ"])
    ctag = os.environ["BEDTIME_CTAG"]

    now_t = parse_hhmm(args.now) if args.now else datetime.now(tz).time()
    in_window = is_within_window(now_t, start_t, end_t)

    status = _request("GET", url + "/control/filtering/status", user, password)
    existing = status.get("user_rules") or []
    desired = compute_rules(existing, in_window, ctag)

    if desired == existing:
        print("bedtime-block: no change (in_window={})".format(in_window))
        return 0

    _request("POST", url + "/control/filtering/set_rules", user, password,
             {"rules": desired})
    print("bedtime-block: updated rules (in_window={})".format(in_window))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ansible/roles/adguard/files && python3 -m unittest test_bedtime_block -v`
Expected: PASS — 12 tests OK.

- [ ] **Step 5: Commit**

```bash
git add ansible/roles/adguard/files/bedtime_block.py ansible/roles/adguard/files/test_bedtime_block.py
git commit -m "feat(adguard): bedtime reconciler script with tested window/rule logic"
```

---

## Task 2: Templated env file and systemd units

**Files:**
- Create: `ansible/roles/adguard/templates/bedtime-block.env.j2`
- Create: `ansible/roles/adguard/templates/adguard-bedtime.service.j2`
- Create: `ansible/roles/adguard/templates/adguard-bedtime.timer.j2`

- [ ] **Step 1: Create the env template**

`ansible/roles/adguard/templates/bedtime-block.env.j2`:

```jinja
ADGUARD_URL=http://127.0.0.1:{{ adguard_http_port }}
ADGUARD_USER={{ adguard_admin_user }}
ADGUARD_PASS={{ adguard_admin_password }}
BEDTIME_START={{ adguard_bedtime_start }}
BEDTIME_END={{ adguard_bedtime_end }}
BEDTIME_TZ={{ adguard_bedtime_timezone }}
BEDTIME_CTAG={{ adguard_bedtime_ctag }}
```

- [ ] **Step 2: Create the service template**

`ansible/roles/adguard/templates/adguard-bedtime.service.j2`:

```jinja
[Unit]
Description=AdGuard internet-bedtime reconciler
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/opt/adguard/bedtime-block.env
ExecStart=/usr/bin/python3 /opt/adguard/bedtime_block.py
```

- [ ] **Step 3: Create the timer template**

`ansible/roles/adguard/templates/adguard-bedtime.timer.j2`:

```jinja
[Unit]
Description=Run the AdGuard internet-bedtime reconciler every {{ adguard_bedtime_interval_min }} min

[Timer]
OnBootSec=2min
OnCalendar=*:0/{{ adguard_bedtime_interval_min }}
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Commit**

```bash
git add ansible/roles/adguard/templates/bedtime-block.env.j2 \
        ansible/roles/adguard/templates/adguard-bedtime.service.j2 \
        ansible/roles/adguard/templates/adguard-bedtime.timer.j2
git commit -m "feat(adguard): bedtime env file + systemd service/timer templates"
```

---

## Task 3: Variables — feature defaults and client inventory

**Files:**
- Modify: `ansible/roles/adguard/defaults/main.yml`
- Modify: `ansible/group_vars/agh/main.yml`

- [ ] **Step 1: Add feature defaults**

Append to `ansible/roles/adguard/defaults/main.yml` (after the sync block at the end):

```yaml

# Internet bedtime — scheduled all-DNS block for clients tagged user_child.
# Reconciler runs on the sync origin only; adguardhome-sync replicates to replicas.
adguard_bedtime_enabled: true
adguard_bedtime_ctag: user_child
adguard_bedtime_start: "01:00"
adguard_bedtime_end: "08:00"
adguard_bedtime_timezone: America/Phoenix
adguard_bedtime_interval_min: 10
```

- [ ] **Step 2: Add the persistent-client inventory**

Append to `ansible/group_vars/agh/main.yml`:

```yaml

# Persistent AdGuard clients (managed in IaC — the Clients UI is now
# authoritative-from-here; UI-only edits are reverted on the next deploy).
# Seeded 2026-06-06 from the live agh1 export. Add `user_child` to a device's
# tags to include it in the nightly internet-bedtime block.
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

- [ ] **Step 3: Sanity-check the YAML parses**

Run: `cd ansible && python3 -c "import yaml; yaml.safe_load(open('group_vars/agh/main.yml')); yaml.safe_load(open('roles/adguard/defaults/main.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add ansible/roles/adguard/defaults/main.yml ansible/group_vars/agh/main.yml
git commit -m "feat(adguard): bedtime defaults + import live persistent clients to IaC"
```

---

## Task 4: Render persistent clients in the config template

**Files:**
- Modify: `ansible/roles/adguard/templates/AdGuardHome.yaml.j2` (clients block ~176-183; global time_zone line 149)

- [ ] **Step 1: Replace the hardcoded empty clients list**

In `ansible/roles/adguard/templates/AdGuardHome.yaml.j2`, replace:

```jinja
  persistent: []
```

with:

```jinja
  persistent:
{% for c in adguard_persistent_clients | default([]) %}
    - name: "{{ c.name }}"
      ids: {{ c.ids | to_json }}
      tags: {{ c.tags | to_json }}
      use_global_settings: true
      use_global_blocked_services: true
      blocked_services:
        schedule:
          time_zone: {{ adguard_bedtime_timezone }}
{% endfor %}
```

- [ ] **Step 2: Align the global blocked-services timezone**

In the same file, replace:

```jinja
      time_zone: America/Los_Angeles
```

with:

```jinja
      time_zone: {{ adguard_bedtime_timezone }}
```

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/adguard/templates/AdGuardHome.yaml.j2
git commit -m "feat(adguard): render persistent clients from inventory; fix timezone"
```

---

## Task 5: Deploy tasks for the reconciler

**Files:**
- Modify: `ansible/roles/adguard/tasks/main.yml` (append at end)

- [ ] **Step 1: Append the bedtime deploy tasks**

Append to `ansible/roles/adguard/tasks/main.yml`:

```yaml

# --- internet bedtime reconciler (sync origin only) ---
- name: Deploy bedtime reconciler script
  ansible.builtin.copy:
    src: bedtime_block.py
    dest: /opt/adguard/bedtime_block.py
    mode: "0755"
  become: true
  when:
    - adguard_bedtime_enabled
    - ansible_host == adguard_sync_origin

- name: Deploy bedtime reconciler env file
  ansible.builtin.template:
    src: bedtime-block.env.j2
    dest: /opt/adguard/bedtime-block.env
    owner: root
    group: root
    mode: "0600"
  become: true
  no_log: true
  when:
    - adguard_bedtime_enabled
    - ansible_host == adguard_sync_origin

- name: Deploy bedtime systemd service unit
  ansible.builtin.template:
    src: adguard-bedtime.service.j2
    dest: /etc/systemd/system/adguard-bedtime.service
    mode: "0644"
  become: true
  when:
    - adguard_bedtime_enabled
    - ansible_host == adguard_sync_origin

- name: Deploy bedtime systemd timer unit
  ansible.builtin.template:
    src: adguard-bedtime.timer.j2
    dest: /etc/systemd/system/adguard-bedtime.timer
    mode: "0644"
  become: true
  when:
    - adguard_bedtime_enabled
    - ansible_host == adguard_sync_origin

- name: Enable and start bedtime timer
  ansible.builtin.systemd:
    name: adguard-bedtime.timer
    enabled: true
    state: started
    daemon_reload: true
  become: true
  when:
    - adguard_bedtime_enabled
    - ansible_host == adguard_sync_origin

- name: Disable bedtime timer when feature is off
  ansible.builtin.systemd:
    name: adguard-bedtime.timer
    enabled: false
    state: stopped
    daemon_reload: true
  become: true
  failed_when: false
  when:
    - not adguard_bedtime_enabled
    - ansible_host == adguard_sync_origin
```

- [ ] **Step 2: Syntax-check the playbook**

Run: `cd ansible && ansible-playbook playbooks/dns/deploy-adguard-config.yml --syntax-check`
Expected: no errors (lists plays).

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/adguard/tasks/main.yml
git commit -m "feat(adguard): deploy bedtime reconciler script, env, and systemd timer"
```

---

## Task 6: Dry-run, deploy, and verify

**Files:** none (operational).

- [ ] **Step 1: Dry-run against agh1**

Run: `cd ansible && ADGUARD_ADMIN_PASSWORD=$(ansible -i inventory/hosts.yml localhost -m debug -a "msg={{ vault_adguard_admin_password }}" -e @group_vars/all/vault.yml 2>/dev/null | grep -oP '(?<="msg": ")[^"]+') ansible-playbook -i inventory/hosts.yml playbooks/dns/deploy-adguard-config.yml --check --diff --limit agh1`
Expected: diffs show the new `clients.persistent` block (9 clients), timezone change, and the new files/units. No errors.

- [ ] **Step 2: Apply to agh1**

Run: same command as Step 1 without `--check`, add `-v`.
Expected: `changed` for the config, script, env, units, and timer; play recap shows `failed=0`.

- [ ] **Step 3: Verify the timer is scheduled**

Run: `ssh -i ~/.ssh/id_ed25519_homelab james@192.168.20.4 systemctl list-timers adguard-bedtime.timer`
Expected: the timer is listed with a NEXT firing time.

- [ ] **Step 4: Verify in-window behavior**

Run: `ssh -i ~/.ssh/id_ed25519_homelab james@192.168.20.4 "sudo bash -c 'set -a; source /opt/adguard/bedtime-block.env; python3 /opt/adguard/bedtime_block.py --now 01:30'"`
Expected: prints `bedtime-block: updated rules (in_window=True)`.
Then: `curl -s -u "$AGH_USER:$AGH_PASS" http://192.168.20.4:3000/control/filtering/status | python3 -c 'import sys,json; print("\n".join(json.load(sys.stdin)["user_rules"]))'`
Expected: includes `! BEGIN bedtime-block`, `*$ctag=user_child`, `! END bedtime-block`.

- [ ] **Step 5: Verify out-of-window behavior (cleanup)**

Run: same command as Step 4 but `--now 12:00`.
Expected: `bedtime-block: updated rules (in_window=False)`; the status `user_rules` no longer contains the bedtime block.

- [ ] **Step 6: Verify replication to agh2**

Wait up to 5 min, then re-run Step 4's in-window command, and after ≤5 min:
Run: `curl -s -u "$AGH_USER:$AGH_PASS" http://192.168.20.5:3000/control/filtering/status | python3 -c 'import sys,json; print("\n".join(json.load(sys.stdin)["user_rules"]))'`
Expected: the bedtime block appears on agh2 too. (Re-run Step 5 afterward to leave rules clean if outside the real window.)

- [ ] **Step 7: Verify idempotence**

Run: Step 1's command again with `--check`.
Expected: `changed=0`.

- [ ] **Step 8: End-to-end (optional, during real window or with --now applied)**

From a `user_child`-tagged device (e.g. 192.168.1.55) using agh1/agh2 as DNS:
Run: `nslookup example.com 192.168.20.4`
Expected: blocked response (`0.0.0.0` / NXDOMAIN) while the rule is active; normal resolution after Step 5 clears it.

---

## Notes for the implementer

- **Run from `ansible/`.** All playbook commands assume that working directory.
- **`$AGH_USER` / `$AGH_PASS`** in verify steps come from vault vars `vault_adguard_admin_username` / `vault_adguard_admin_password` (see CLAUDE.md credential access). Do not hardcode them in any committed file.
- **Sync origin only:** the timer is intentionally deployed on agh1 (`adguard_sync_origin`) and not agh2. This is by design — see the spec's "single writer" rationale.
- **Leave rules clean:** if you toggle with `--now` outside the real 01:00–08:00 window during testing, finish with a `--now 12:00` run so you don't leave the block active.
