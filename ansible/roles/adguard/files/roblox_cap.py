#!/usr/bin/env python3
"""AdGuard Roblox daily-cap reconciler.

Counts today's Roblox DNS activity in fixed local-time buckets and toggles the
built-in global Roblox blocked service when usage exceeds the configured cap.

Config via environment:
  ADGUARD_URL, ADGUARD_USER, ADGUARD_PASS
  ROBLOX_CAP_TZ, ROBLOX_CAP_LOG_PATH
  ROBLOX_CAP_BUCKET_MIN, ROBLOX_CAP_BUCKET_LIMIT
  ROBLOX_CAP_SERVICE_ID
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ROBLOX_MATCHES = ("roblox.com", "rbxcdn.com", "rbx.com")


def is_roblox_query(host):
    host = (host or "").lower()
    return any(token in host for token in ROBLOX_MATCHES)


def _bucket_key(dt, bucket_min):
    dt = dt.replace(second=0, microsecond=0)
    minute = (dt.minute // bucket_min) * bucket_min
    return dt.replace(minute=minute)


def count_active_buckets(lines, now_dt, tz, bucket_min):
    today = now_dt.astimezone(tz).date()
    buckets = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            host = obj.get("QH")
            ts = obj.get("T")
            if not is_roblox_query(host) or not ts:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
        except (ValueError, json.JSONDecodeError, TypeError):
            continue
        if dt.date() != today:
            continue
        buckets.add(_bucket_key(dt, bucket_min))
    return len(buckets)


def compute_ids(existing_ids, should_block, service_id):
    ids = [item for item in existing_ids if item != service_id]
    if should_block:
        ids.append(service_id)
    return ids


def _request(method, url, user, password, data=None):
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers["Authorization"] = "Basic " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="ISO timestamp override for testing")
    args = ap.parse_args(argv)

    url = os.environ["ADGUARD_URL"].rstrip("/")
    user = os.environ["ADGUARD_USER"]
    password = os.environ["ADGUARD_PASS"]
    tz = ZoneInfo(os.environ["ROBLOX_CAP_TZ"])
    log_path = os.environ["ROBLOX_CAP_LOG_PATH"]
    bucket_min = int(os.environ["ROBLOX_CAP_BUCKET_MIN"])
    bucket_limit = int(os.environ["ROBLOX_CAP_BUCKET_LIMIT"])
    service_id = os.environ["ROBLOX_CAP_SERVICE_ID"]

    now_dt = (
        datetime.fromisoformat(args.now).astimezone(tz)
        if args.now
        else datetime.now(tz)
    )

    with open(log_path, encoding="utf-8") as fh:
        bucket_count = count_active_buckets(fh, now_dt, tz, bucket_min)

    should_block = bucket_count >= bucket_limit

    current = _request("GET", url + "/control/blocked_services/get", user, password)
    existing_ids = current.get("ids") or []
    desired_ids = compute_ids(existing_ids, should_block, service_id)

    if desired_ids == existing_ids:
        print(
            "roblox-cap: no change (buckets={}, limit={}, blocked={})".format(
                bucket_count, bucket_limit, should_block
            )
        )
        return 0

    _request("POST", url + "/control/blocked_services/set", user, password, desired_ids)
    print(
        "roblox-cap: updated blocked services (buckets={}, limit={}, blocked={})".format(
            bucket_count, bucket_limit, should_block
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
