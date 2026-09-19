from __future__ import annotations

import unittest

from market_sentinel_ai.releases import CURRENT_RELEASE, RELEASE_PLAN


class ReleasePlanTests(unittest.TestCase):
    def test_plan_has_eight_releases(self) -> None:
        self.assertEqual(len(RELEASE_PLAN), 8)
        self.assertEqual(RELEASE_PLAN[0].code, "R0")
        self.assertEqual(RELEASE_PLAN[-1].version, "1.0.0")

    def test_versions_are_unique(self) -> None:
        versions = [release.version for release in RELEASE_PLAN]
        self.assertEqual(len(versions), len(set(versions)))

    def test_current_release_is_r7(self) -> None:
        self.assertEqual(CURRENT_RELEASE.code, "R7")
        self.assertEqual(CURRENT_RELEASE.version, "1.0.0")


if __name__ == "__main__":
    unittest.main()
