from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from lib.contracts import EventType, GatewayEvent, ServiceHealth, SystemStatus


@dataclass(frozen=True)
class ServiceMetrics:
    latency_ms: float
    error_rate: float
    health: ServiceHealth
    hp: int = 100


def _hp_from_metrics(latency_ms: float, error_rate: float, halted: bool) -> int:
    if halted:
        return 0
    latency_penalty = min(40, int(latency_ms / 25.0))
    error_penalty = min(60, int(error_rate * 100.0))
    return max(0, 100 - latency_penalty - error_penalty)


def evaluate_service_health(latency_ms: float, error_rate: float, system_status: SystemStatus) -> ServiceMetrics:
    if system_status in {SystemStatus.OUTAGE, SystemStatus.UNKNOWN}:
        return ServiceMetrics(latency_ms=latency_ms, error_rate=error_rate, health=ServiceHealth.HALTED, hp=0)

    if error_rate >= 0.2 or latency_ms >= 800.0:
        health = ServiceHealth.UNDER_ATTACK
    elif error_rate >= 0.08 or latency_ms >= 250.0:
        health = ServiceHealth.DEGRADED
    else:
        health = ServiceHealth.HEALTHY

    hp = _hp_from_metrics(latency_ms=latency_ms, error_rate=error_rate, halted=health == ServiceHealth.HALTED)
    return ServiceMetrics(latency_ms=latency_ms, error_rate=error_rate, health=health, hp=hp)


class CombatEventFactory:
    @staticmethod
    def _build(
        event_type: EventType,
        message: str,
        details: Optional[Dict[str, object]] = None,
        severity: str = "WARNING",
    ) -> GatewayEvent:
        return GatewayEvent(
            type=event_type,
            message=message,
            details=details or {},
            severity=severity,
            timestamp=datetime.now().isoformat(),
        )

    @classmethod
    def from_test_failures(cls, service_id: str, service_name: str, failures: int) -> Optional[GatewayEvent]:
        if failures <= 0:
            return None
        return cls._build(
            event_type=EventType.BUG_SPAWNED,
            message=f"{failures} failing tests spawned bugs for {service_name}",
            severity="WARNING" if failures < 5 else "CRITICAL",
            details={"service_id": service_id, "service_name": service_name, "failures": failures, "source": "failed_tests"},
        )

    @classmethod
    def from_worker_errors(cls, service_id: str, service_name: str, errors: int) -> Optional[GatewayEvent]:
        if errors <= 0:
            return None
        return cls._build(
            event_type=EventType.SERVICE_DAMAGED,
            message=f"Worker instability damaged {service_name}",
            severity="CRITICAL",
            details={"service_id": service_id, "service_name": service_name, "errors": errors, "source": "worker_errors"},
        )

    @classmethod
    def from_budget_utilization(
        cls,
        service_id: str,
        service_name: str,
        budget_utilization_percent: float,
    ) -> List[GatewayEvent]:
        if budget_utilization_percent < 90.0:
            return []
        return [
            cls._build(
                event_type=EventType.SERVICE_DAMAGED,
                message=f"Critical budget pressure affecting {service_name}",
                severity="CRITICAL",
                details={
                    "service_id": service_id,
                    "service_name": service_name,
                    "budget_utilization_percent": round(budget_utilization_percent, 2),
                    "source": "budget_critical",
                },
            )
        ]

    @classmethod
    def from_service_transition(
        cls,
        service_id: str,
        service_name: str,
        previous: ServiceMetrics,
        current: ServiceMetrics,
        system_status: SystemStatus,
    ) -> List[GatewayEvent]:
        if previous.health in {ServiceHealth.DEGRADED, ServiceHealth.UNDER_ATTACK, ServiceHealth.HALTED} and (
            current.health == ServiceHealth.HEALTHY and system_status == SystemStatus.OPERATIONAL
        ):
            return [
                cls._build(
                    event_type=EventType.SERVICE_RECOVERED,
                    message=f"{service_name} recovered to healthy",
                    severity="INFO",
                    details={
                        "service_id": service_id,
                        "service_name": service_name,
                        "previous_health": previous.health.value,
                        "current_health": current.health.value,
                        "hp": current.hp,
                    },
                )
            ]
        return []
