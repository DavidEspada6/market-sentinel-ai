from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.domain.reasoning import ReasoningResult


class ReasoningCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._items: dict[str, ReasoningResult] = {}
        if self.path is not None and self.path.exists():
            self._load()

    def key_for(self, signal: Signal, context: dict[str, object]) -> str:
        payload = {
            "signal_id": self.signal_id(signal),
            "direction": signal.prediction.direction.value,
            "confidence": round(signal.confidence, 6),
            "context": context,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def signal_id(self, signal: Signal) -> str:
        payload = {
            "symbol": signal.prediction.symbol,
            "direction": signal.prediction.direction.value,
            "generated_at": signal.prediction.generated_at.isoformat(),
            "model": signal.prediction.model_name,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def get(self, key: str) -> ReasoningResult | None:
        return self._items.get(key)

    def set(self, key: str, value: ReasoningResult) -> None:
        self._items[key] = value
        if self.path is not None:
            self._save()

    def _load(self) -> None:
        assert self.path is not None
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for key, value in raw.items():
            self._items[key] = ReasoningResult(
                signal_id=value["signal_id"],
                generated_at=datetime.fromisoformat(value["generated_at"]),
                thesis=value["thesis"],
                invalidation=value["invalidation"],
                risk_notes=tuple(value["risk_notes"]),
                context_sources=tuple(value["context_sources"]),
                raw_cost_tokens_estimate=value["raw_cost_tokens_estimate"],
            )

    def _save(self) -> None:
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            key: {
                **asdict(value),
                "generated_at": value.generated_at.isoformat(),
                "risk_notes": list(value.risk_notes),
                "context_sources": list(value.context_sources),
            }
            for key, value in self._items.items()
        }
        self.path.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")

