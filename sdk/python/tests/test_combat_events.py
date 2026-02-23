import unittest

from lib.combat_events import (
    CombatEventFactory,
    ServiceMetrics,
    evaluate_service_health,
)
from lib.contracts import EventType, ServiceHealth, SystemStatus


class CombatEventsTests(unittest.TestCase):
    def test_build_bug_spawned_from_test_failures(self):
        event = CombatEventFactory.from_test_failures(service_id="svc", service_name="gateway", failures=4)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.type, EventType.BUG_SPAWNED)
        self.assertEqual(event.details["source"], "failed_tests")

    def test_worker_errors_trigger_damage(self):
        event = CombatEventFactory.from_worker_errors(service_id="svc", service_name="gateway", errors=2)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.type, EventType.SERVICE_DAMAGED)
        self.assertEqual(event.severity, "CRITICAL")

    def test_budget_critical_triggers_damage(self):
        events = CombatEventFactory.from_budget_utilization(
            service_id="svc",
            service_name="gateway",
            budget_utilization_percent=93.5,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.SERVICE_DAMAGED)

    def test_recovered_event_is_emitted_when_service_back_to_healthy(self):
        previous = ServiceMetrics(latency_ms=400.0, error_rate=0.3, health=ServiceHealth.HALTED)
        current = ServiceMetrics(latency_ms=50.0, error_rate=0.01, health=ServiceHealth.HEALTHY)

        events = CombatEventFactory.from_service_transition(
            service_id="svc",
            service_name="gateway",
            previous=previous,
            current=current,
            system_status=SystemStatus.OPERATIONAL,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.SERVICE_RECOVERED)

    def test_service_health_becomes_halted_when_system_halted(self):
        result = evaluate_service_health(
            latency_ms=10.0,
            error_rate=0.0,
            system_status=SystemStatus.OUTAGE,
        )
        self.assertEqual(result.health, ServiceHealth.HALTED)
        self.assertEqual(result.hp, 0)


if __name__ == "__main__":
    unittest.main()
