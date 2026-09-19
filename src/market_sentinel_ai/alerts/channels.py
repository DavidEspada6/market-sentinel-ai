from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from market_sentinel_ai.domain.prediction import Signal


@dataclass
class DryRunAlertChannel:
    sent: list[Signal] = field(default_factory=list)

    @property
    def channel_name(self) -> str:
        return "dry-run"

    def send(self, signal: Signal) -> str:
        self.sent.append(signal)
        return f"dry-run-{len(self.sent)}"


class JsonlAlertChannel:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def channel_name(self) -> str:
        return "jsonl"

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


class WebhookAlertChannel:
    def __init__(self, url: str, timeout_seconds: float = 10.0) -> None:
        if not url.strip():
            raise ValueError("url cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.url = url
        self.timeout_seconds = timeout_seconds

    @property
    def channel_name(self) -> str:
        return "webhook"

    def send(self, signal: Signal) -> str:
        import urllib.request

        payload = {
            "symbol": signal.prediction.symbol,
            "direction": signal.prediction.direction.value,
            "confidence": signal.confidence,
            "probability": signal.prediction.probability,
            "model_name": signal.prediction.model_name,
            "rationale": signal.rationale,
            "risk_notes": list(signal.risk_notes),
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status >= 300:
                raise RuntimeError(f"webhook returned HTTP {response.status}")
        return f"webhook-{datetime.now(tz=UTC).timestamp():.6f}"
