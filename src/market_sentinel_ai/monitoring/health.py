from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class HealthRepository(Protocol):
    def health_status(self) -> dict[str, object]:
        """Return a database health status."""

    def record_health_check(
        self,
        check_name: str,
        status: str,
        details: dict[str, object],
    ) -> str:
        """Persist one health check."""


@dataclass(frozen=True)
class HealthReport:
    status: str
    checked_at: datetime
    checks: dict[str, dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checked_at": self.checked_at.isoformat(),
            "real_orders_enabled": False,
            "checks": self.checks,
        }


class HealthService:
    def __init__(self, repository: HealthRepository) -> None:
        self.repository = repository

    def check(self) -> HealthReport:
        database = self.repository.health_status()
        checks = {
            "database": database,
            "paper_execution": {
                "status": "disabled",
                "real_orders_enabled": False,
            },
        }
        status = "ok" if database.get("status") == "ok" else "degraded"
        report = HealthReport(status=status, checked_at=datetime.now(tz=UTC), checks=checks)
        self.repository.record_health_check("application", report.status, report.to_dict())
        return report
