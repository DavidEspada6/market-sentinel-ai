from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True)
class AstraUsageSnapshot:
    day: date
    requests: int
    cache_hits: int
    input_tokens_estimate: int
    output_tokens_estimate: int
    estimated_cost_usd: float


class AstraUsageLedger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None

    def snapshot(self, now: datetime | None = None) -> AstraUsageSnapshot:
        current_day = (now or datetime.now(tz=UTC)).date()
        totals = {
            "requests": 0,
            "cache_hits": 0,
            "input_tokens_estimate": 0,
            "output_tokens_estimate": 0,
            "estimated_cost_usd": 0.0,
        }
        if self.path is None or not self.path.exists():
            return AstraUsageSnapshot(current_day, **totals)
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("day") != current_day.isoformat():
                continue
            for key in totals:
                totals[key] += record.get(key, 0)
        return AstraUsageSnapshot(current_day, **totals)

    def record(
        self,
        *,
        status: str,
        signal_id: str,
        input_tokens_estimate: int,
        output_tokens_estimate: int,
        estimated_cost_usd: float,
        now: datetime | None = None,
    ) -> None:
        if self.path is None:
            return
        timestamp = now or datetime.now(tz=UTC)
        record = {
            "created_at": timestamp.isoformat(),
            "day": timestamp.date().isoformat(),
            "status": status,
            "signal_id": signal_id,
            "requests": int(status == "requested"),
            "cache_hits": int(status == "cache_hit"),
            "input_tokens_estimate": input_tokens_estimate,
            "output_tokens_estimate": output_tokens_estimate,
            "estimated_cost_usd": estimated_cost_usd,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
