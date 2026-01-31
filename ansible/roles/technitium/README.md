# Technitium role (tt1 primary, tt2 secondary)

Purpose: push pre-exported Technitium data (config.json, zones/, DHCP data) onto the DNS LXCs and optionally restart the container. Use this to keep DNS/DHCP boilerplate in git and reapply after changes.

Workflow
1) Export current tt1 data directory to a local path you set as `technitium_data_src` (do NOT commit secrets elsewhere):
   ```bash
   # on tt1
   sudo rsync -av /opt/dns/data/technitium/ /tmp/technitium-export/
   # copy /tmp/technitium-export somewhere locally; set technitium_data_src to that path
   ```
2) Ensure `TECHNITIUM_ADMIN_PASSWORD` and TSIG keys live in vault/1Password; keep them out of the repo.
3) Run the role against tt1/tt2 (example inventory groups `tt`): 
   ```yaml
   - hosts: tt
     become: true
     roles:
       - role: technitium
         technitium_data_src: /path/to/technitium-export
         technitium_data_dest: /opt/dns/data/technitium
         technitium_restart_cmd: "cd /opt/dns && docker compose restart technitium"
   ```

Defaults (override as needed)
- `technitium_data_src`: local path to exported data (default: null, must be set to sync)
- `technitium_data_dest`: remote data path (`/opt/dns/data/technitium`)
- `technitium_owner` / `technitium_group`: file ownership (root/root)
- `technitium_restart`: true to restart container after sync
- `technitium_restart_cmd`: restart command (defaults to `docker restart technitium`)
- `technitium_rsync_include`: patterns to include (default config.json, zones/***, dhcp/***)
- `technitium_rsync_exclude`: patterns to exclude (default excludes logs/stats/tmp)
- `technitium_rsync_delete`: false (set true to delete extraneous files in dest)

Notes
- This role is file-based; it does not generate JSON/templates. Keep the exported data current after UI changes.
- TSIG keys and admin password must be managed via secrets, not checked into git.
- To dry-run without restart, set `technitium_restart: false`.
- The sync uses rsync with includes (config/zones/dhcp) and excludes logs/stats by default; delete is off unless you enable it. It is no-op unless you set `technitium_data_src`.
