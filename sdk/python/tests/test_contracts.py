import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.contracts import (
    CharacterLoadout,
    CharacterProfile,
    CharacterLoadoutSelection,
    ControlCommand,
    ControlCommandType,
    DocPackRef,
    PromptProfileRef,
    SkillSelection,
    ToolLoadout,
    EventType,
    GameState,
    GatewayEvent,
    GraphData,
    LoadoutAction,
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
            "countries": [
                {
                    "id": "country-core",
                    "name": "The Core Empire",
                    "services": [
                        {"id": "service-gateway", "name": "gateway", "health": "degraded", "hp": 77, "latency_ms": 321.0, "error_rate": 0.14}
                    ],
                }
            ],
        }

        model = GameState.model_validate(payload)

        self.assertEqual(model.system_status, SystemStatus.OPERATIONAL)
        self.assertEqual(model.active_quests[0].status, QuestStatus.IN_PROGRESS)

        serialized = model.model_dump(by_alias=True)
        self.assertEqual(serialized["party"][0]["class"], "Warrior")
        self.assertEqual(serialized["countries"][0]["services"][0]["hp"], 77)


    def test_game_state_requires_country_service_minimum_fields(self):
        payload = {
            "system_status": "OPERATIONAL",
            "daily_budget": {"max": 10.0, "spent": 2.5, "unit": "USD"},
            "party": [],
            "active_quests": [],
            "fog_map": {},
            "repositories": [],
            "countries": [{"id": "country-core", "name": "The Core Empire", "services": [{}]}],
        }

        with self.assertRaises(Exception):
            GameState.model_validate(payload)

    def test_graph_data_round_trip(self):
        graph = GraphData.model_validate(
            {
                "nodes": [{"id": "a", "label": "A", "type": "subject"}],
                "edges": [{"source": "a", "target": "b", "label": "depends_on"}],
            }
        )

        self.assertEqual(graph.nodes[0].node_type, "subject")
        self.assertEqual(graph.model_dump(by_alias=True)["nodes"][0]["type"], "subject")

    def test_character_profile_contract(self):
        profile = CharacterProfile(
            id="char-coder",
            agent_id="agent-coder",
            display_name="Coder",
            class_name="Warrior",
            level=5,
            location="The Shell Dungeon",
            loadout=CharacterLoadout(
                primary_weapon="Refactor Blade",
                secondary_item="Debugger Lantern",
                armor="Terminal Plate",
                hit_points=100,
                mana=80,
            ),
        )

        self.assertEqual(profile.loadout.primary_weapon, "Refactor Blade")
        self.assertEqual(profile.level, 5)


    def test_control_command_supports_typed_loadout(self):
        command = ControlCommand(
            command=ControlCommandType.CONFIGURE_CHARACTER_LOADOUT,
            agent_id="agent-1",
            payload_version="v2",
            loadout=CharacterLoadoutSelection(
                prompt_profile=PromptProfileRef(profile_id="prompt.default", version="2025-01"),
                tool_loadout=ToolLoadout(loadout_id="tools.core", tool_ids=["search", "build"]),
                doc_packs=[DocPackRef(pack_id="docs.arch", version="1")],
                skills=[SkillSelection(skill_id="skill-creator", enabled=True)],
            ),
        )

        self.assertEqual(command.command, ControlCommandType.CONFIGURE_CHARACTER_LOADOUT)
        self.assertEqual(command.loadout.prompt_profile.profile_id, "prompt.default")
        self.assertEqual(command.model_dump()["payload_version"], "v2")

    def test_control_command_and_event_serialization(self):
        command = ControlCommand(command=ControlCommandType.ASSIGN_MISSION, agent_id="agent-1", repo_id="repo-1", task="Fix")
        self.assertEqual(command.command, ControlCommandType.ASSIGN_MISSION)

        event = GatewayEvent(type=EventType.BUG_SPAWNED, message="Bug wave")
        self.assertEqual(event.type, EventType.BUG_SPAWNED)

    def test_loadout_action_enum_values_are_stable(self):
        self.assertEqual(LoadoutAction.APPLY.value, "apply")
        self.assertEqual(LoadoutAction.CONFIRM.value, "confirm")


if __name__ == "__main__":
    unittest.main()
