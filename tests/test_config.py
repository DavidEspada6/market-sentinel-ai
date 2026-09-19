from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_sentinel_ai.config import Settings


class SettingsTests(unittest.TestCase):
    def test_openai_is_disabled_without_api_key(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.openai.model, "gpt-6-astra")
        self.assertFalse(settings.openai.enabled)
        self.assertTrue(settings.alerts.dry_run)

    def test_risk_settings_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"RISK_MAX_POSITION_PCT": "0.01"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.risk.max_position_pct, 0.01)


if __name__ == "__main__":
    unittest.main()

