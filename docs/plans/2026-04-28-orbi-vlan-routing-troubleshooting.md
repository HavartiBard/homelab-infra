# Orbi / VLAN Routing Troubleshooting Findings

**Issue:** Homelab/homelab-infra#79
**Status:** Investigation documented; next code patch still needed in the homelab-mcp service repo

## Summary

We traced the VLAN routing complaint to the Orbi / client-policy layer rather than to the DNS servers themselves.

Evidence collected so far indicates:
- the DNS hosts with VLAN interfaces are routing normally
- UDP reachability to the Bedrock host works from all tested DNS-server VLAN source IPs
- the Orbi exposes a likely VLAN isolation flag on `lan2`
- the Orbi attached-devices lookup fails with a generic error, hiding the underlying router/API failure

## Findings

### DNS server / VLAN interface behavior
- `tt1` has interfaces on VLAN 1, VLAN 20, and VLAN 30.
- From `tt1`, UDP connectivity to `192.168.20.14:19132` works from the VLAN 1, VLAN 20, and VLAN 30 source addresses.
- That makes the DNS host side of the routing path look healthy.

### Orbi policy clues
- The Orbi profile state shows:
  - `network_isolation = 0`
  - `client_isolation = 0`
  - `lan2 = 192.168.20.1` with `isolate = 1`
- That `lan2` isolate flag is the strongest clue that the remaining problem is router-side policy / VLAN isolation.

### Orbi diagnostics gap
- `orbi_get_attached_devices()` currently returns a generic failure payload instead of exposing the underlying SOAP/auth error.
- Direct access to `192.168.1.1` reaches the router, but the web UI returns `401 Authorization` without valid credentials.
- Because the attached-device call collapses failures into one generic result, it is hard to tell whether the router is rejecting the SOAP request, the endpoint changed, or the wrapper is masking a lower-level exception.

## Next steps

1. Patch the homelab-mcp Orbi integration so the attached-devices path reports the actual failing SOAP method and exception text.
2. Preserve successful empty responses as distinct from hard failures.
3. Re-test whether `lan2 isolate = 1` is intentional or a misconfiguration.
4. If router access becomes available, verify whether VLAN 20 clients are being blocked at the Orbi rather than at the DNS servers.

## Related tracking

- Gitea issue: **#79**
- Recommended code change target: the `homelab_mcp/services/orbi/service.py` path in the homelab-mcp service codebase

## Notes

- No secrets are included in this document.
- This note is meant to document the investigation and keep the next implementation step grounded in the observed behavior.
