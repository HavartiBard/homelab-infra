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
