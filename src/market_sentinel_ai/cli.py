from __future__ import annotations

import json

from market_sentinel_ai.config import Settings
from market_sentinel_ai.releases import RELEASE_PLAN


def main() -> None:
    settings = Settings.from_env()
    payload = {
        "app": "Market Sentinel AI",
        "environment": settings.environment,
        "astra_model": settings.openai.model,
        "astra_enabled": settings.openai.enabled,
        "current_release": RELEASE_PLAN[0].code,
        "planned_releases": [release.code for release in RELEASE_PLAN],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

