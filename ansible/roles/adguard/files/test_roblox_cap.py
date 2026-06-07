import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import roblox_cap as r


class RobloxCapTests(unittest.TestCase):
    def test_matches_known_roblox_domains(self):
        self.assertTrue(r.is_roblox_query("ecsv2.roblox.com"))
        self.assertTrue(r.is_roblox_query("assetgame.roblox.com"))
        self.assertTrue(r.is_roblox_query("setup.rbxcdn.com"))
        self.assertTrue(r.is_roblox_query("apis.rbx.com"))
        self.assertFalse(r.is_roblox_query("www.google.com"))

    def test_counts_unique_buckets_for_today_only(self):
        tz = ZoneInfo("America/Phoenix")
        now_dt = datetime(2026, 6, 7, 18, 0, tzinfo=tz)
        lines = [
            '{"T":"2026-06-07T15:01:00Z","QH":"ecsv2.roblox.com"}',
            '{"T":"2026-06-07T15:03:00Z","QH":"apis.roblox.com"}',
            '{"T":"2026-06-07T15:07:00Z","QH":"setup.rbxcdn.com"}',
            '{"T":"2026-06-06T23:59:00Z","QH":"ecsv2.roblox.com"}',
            '{"T":"2026-06-07T15:20:00Z","QH":"www.google.com"}',
        ]
        self.assertEqual(r.count_active_buckets(lines, now_dt, tz, 5), 2)

    def test_crosses_midnight_in_local_timezone(self):
        tz = ZoneInfo("America/Phoenix")
        now_dt = datetime(2026, 6, 7, 1, 0, tzinfo=tz)
        lines = [
            '{"T":"2026-06-07T06:30:00Z","QH":"ecsv2.roblox.com"}',
            '{"T":"2026-06-07T07:30:00Z","QH":"ecsv2.roblox.com"}',
        ]
        self.assertEqual(r.count_active_buckets(lines, now_dt, tz, 5), 1)

    def test_compute_ids_adds_roblox_when_over_limit(self):
        self.assertEqual(
            r.compute_ids(["youtube"], True, "roblox"), ["youtube", "roblox"]
        )

    def test_compute_ids_removes_roblox_when_under_limit(self):
        self.assertEqual(
            r.compute_ids(["youtube", "roblox"], False, "roblox"), ["youtube"]
        )

    def test_compute_ids_is_idempotent(self):
        self.assertEqual(r.compute_ids(["roblox"], True, "roblox"), ["roblox"])


if __name__ == "__main__":
    unittest.main()
