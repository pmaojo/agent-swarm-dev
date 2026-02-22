import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.contracts import (
    ControlCommand,
    ControlCommandType,
    EventType,
    GameState,
    GatewayEvent,
    GraphData,
    QuestStatus,
    SystemStatus,
)


class ContractSerializationTests(unittest.TestCase):
    def test_game_state_round_trip(self):
        payload = {
            "system_status": "OPERATIONAL",
            "daily_budget": {"max": 10.0, "spent": 2.5, "unit": "USD"},
            "party": [
                {
                    "id": "agent-coder",
                    "name": "Coder",
                    "class": "Warrior",
                    "level": 5,
                    "stats": {"hp": 100, "mana": 80, "success_rate": "95%"},
                    "current_action": "Idle",
                    "location": "Citadel",
                }
            ],
            "active_quests": [{"id": "q-1", "title": "Implement API", "status": "IN_PROGRESS"}],
            "fog_map": {},
            "repositories": [{"id": "repo-main", "name": "Main", "swarm": ["agent-coder"]}],
        }

        model = GameState.model_validate(payload)

        self.assertEqual(model.system_status, SystemStatus.OPERATIONAL)
        self.assertEqual(model.active_quests[0].status, QuestStatus.IN_PROGRESS)

        serialized = model.model_dump(by_alias=True)
        self.assertEqual(serialized["party"][0]["class"], "Warrior")

    def test_graph_data_round_trip(self):
        graph = GraphData.model_validate(
            {
                "nodes": [{"id": "a", "label": "A", "type": "subject"}],
                "edges": [{"source": "a", "target": "b", "label": "depends_on"}],
            }
        )

        self.assertEqual(graph.nodes[0].node_type, "subject")
        self.assertEqual(graph.model_dump(by_alias=True)["nodes"][0]["type"], "subject")

    def test_control_command_and_event_serialization(self):
        command = ControlCommand(command=ControlCommandType.ASSIGN_MISSION, agent_id="agent-1", repo_id="repo-1", task="Fix")
        self.assertEqual(command.command, ControlCommandType.ASSIGN_MISSION)

        event = GatewayEvent(type=EventType.HARDENING_EVENT, message="Contract failure")
        self.assertEqual(event.type, EventType.HARDENING_EVENT)


if __name__ == "__main__":
    unittest.main()
