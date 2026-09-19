from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class JsonlEventLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, payload: dict[str, object]) -> None:
        record = {
            "event_type": event_type,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")

