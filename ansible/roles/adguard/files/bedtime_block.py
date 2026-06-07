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
