from __future__ import annotations

import unittest
from importlib.metadata import version

from market_sentinel_ai.releases import (
    COMPLETION_PLAN,
    CURRENT_RELEASE,
    FOLLOW_ON_PLAN,
    RELEASE_PLAN,
)


class ReleasePlanTests(unittest.TestCase):
    def test_plan_has_eight_releases(self) -> None:
        self.assertEqual(len(RELEASE_PLAN), 8)
        self.assertEqual(RELEASE_PLAN[0].code, "R0")
        self.assertEqual(RELEASE_PLAN[-1].version, "1.0.0")

    def test_versions_are_unique(self) -> None:
        versions = [release.version for release in RELEASE_PLAN]
        self.assertEqual(len(versions), len(set(versions)))

    def test_completion_plan_ends_at_v2(self) -> None:
        self.assertEqual(COMPLETION_PLAN[0].version, "1.1.0")
        self.assertEqual(COMPLETION_PLAN[-1].version, "2.0.0")

    def test_follow_on_plan_and_current_release(self) -> None:
        self.assertEqual(FOLLOW_ON_PLAN[0].code, "O1")
        self.assertEqual(FOLLOW_ON_PLAN[-1].version, "3.0.0")
        self.assertEqual(CURRENT_RELEASE.code, "O5")
        self.assertEqual(CURRENT_RELEASE.version, "2.5.0")
        self.assertEqual(version("market-sentinel-ai"), CURRENT_RELEASE.version)


if __name__ == "__main__":
    unittest.main()
