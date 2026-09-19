from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest


class CliSmokeTests(unittest.TestCase):
    def test_status_command_outputs_current_release(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "market_sentinel_ai", "status"],
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["current_release"], "C1")

    def test_astra_context_demo_has_no_key_path(self) -> None:
        env = {**os.environ, "OPENAI_API_KEY": ""}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "market_sentinel_ai",
                "astra-context-demo",
                "--symbol",
                "SPY",
                "--timeframe",
                "5m",
                "--days",
                "1",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

        payload = json.loads(result.stdout)
        self.assertFalse(payload["astra_enabled"])
        self.assertIn("signal_direction", payload)


if __name__ == "__main__":
    unittest.main()
