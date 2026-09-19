from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from market_sentinel_ai.domain.prediction import Signal


@dataclass
class DryRunAlertChannel:
    sent: list[Signal] = field(default_factory=list)

    def send(self, signal: Signal) -> str:
        self.sent.append(signal)
        return f"dry-run-{len(self.sent)}"


class JsonlAlertChannel:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, signal: Signal) -> str:
        alert_id = f"jsonl-{datetime.now(tz=UTC).timestamp():.6f}"
        record = {
            "alert_id": alert_id,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "symbol": signal.prediction.symbol,
            "direction": signal.prediction.direction.value,
            "confidence": signal.confidence,
            "probability": signal.prediction.probability,
            "model_name": signal.prediction.model_name,
            "rationale": signal.rationale,
            "risk_notes": list(signal.risk_notes),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return alert_id

