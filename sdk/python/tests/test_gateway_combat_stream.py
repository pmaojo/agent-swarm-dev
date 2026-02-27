import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()

sys.modules['agents.synapse_proto.codegraph_pb2'] = MagicMock()
sys.modules['agents.synapse_proto.codegraph_pb2_grpc'] = MagicMock()

with patch('agents.orchestrator.OrchestratorAgent') as MockOrch:
    instance = MockOrch.return_value
    instance.agents = {"Coder": {}, "Reviewer": {}}
    instance.check_operational_status.return_value = "OPERATIONAL"
    instance.query_graph.return_value = [{"count": "0"}]
    instance.bridge.get_cards_in_list.return_value = []
    instance.ingest_triples.return_value = None

    import lib.gateway_runtime as gateway_runtime
    from lib.character_profiles import CharacterRegistry, JsonCharacterProfileSink, JsonCharacterProfileSource
    from lib.gateway_runtime import app, combat_event_queue, character_registry, fetch_game_state


class CombatStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_combat_stream_receives_published_event(self) -> None:
        combat_event_queue.put_nowait({
            "type": "BUG_SPAWNED",
            "payload": {"type": "BUG_SPAWNED", "message": "spawn", "details": {}, "severity": "WARNING", "timestamp": "t"},
        })

        with self.client.websocket_connect('/api/v1/events/combat/stream') as websocket:
            message = websocket.receive_json()

        self.assertEqual(message["type"], "BUG_SPAWNED")

    def test_character_endpoints_support_listing_and_selecting(self) -> None:
        list_response = self.client.get('/api/v1/characters')
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertTrue(len(payload["characters"]) > 0)

        first_character_id = payload["characters"][0]["id"]
        select_response = self.client.post('/api/v1/characters/select', json={"character_id": first_character_id})
        self.assertEqual(select_response.status_code, 200)
        self.assertEqual(select_response.json()["selected_character_id"], first_character_id)


    def test_control_command_accepts_typed_loadout_payload(self) -> None:
        response = self.client.post('/api/v1/control/commands', json={
            "command": "CONFIGURE_CHARACTER_LOADOUT",
            "agent_id": "agent-coder",
            "payload_version": "v2",
            "loadout": {
                "prompt_profile": {"profile_id": "prompt.default", "version": "2025-01"},
                "tool_loadout": {"loadout_id": "tools.core", "tool_ids": ["search", "build"]},
                "doc_packs": [{"pack_id": "docs.arch", "version": "1"}],
                "skills": [{"skill_id": "skill-creator", "enabled": True}]
            },
            "metadata": {"source": "godot-war-room"}
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()["command"]
        self.assertEqual(payload["command"], "CONFIGURE_CHARACTER_LOADOUT")
        self.assertEqual(payload["loadout"]["prompt_profile"]["profile_id"], "prompt.default")

    def test_control_command_rejects_invalid_loadout_shape(self) -> None:
        response = self.client.post('/api/v1/control/commands', json={
            "command": "CONFIGURE_CHARACTER_LOADOUT",
            "agent_id": "agent-coder",
            "payload_version": "v2",
            "loadout": {
                "prompt_profile": {"id": "missing-profile-id-field"}
            }
        })

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertIn("Invalid loadout payload", payload["detail"])

    def test_loadout_endpoint_persists_selection_in_game_state(self) -> None:
        characters = self.client.get('/api/v1/characters').json()["characters"]
        character_id = characters[0]["id"]

        save_response = self.client.post('/api/v1/characters/loadout', json={
            "character_id": character_id,
            "action": "apply",
            "loadout": {
                "prompt_profile": {"profile_id": "prompt.reviewer", "version": "2026-01"},
                "tool_loadout": {"loadout_id": "tools.review", "tool_ids": ["search", "test", "lint"]},
                "doc_packs": [{"pack_id": "docs.security", "version": "2"}],
                "skills": [{"skill_id": "skill-creator", "enabled": True}],
            },
        })

        self.assertEqual(save_response.status_code, 200)
        game_state = self.client.get('/api/v1/game-state').json()
        self.assertEqual(game_state["selected_character_id"], character_id)
        self.assertEqual(game_state["selected_character_loadout"]["prompt_profile"]["profile_id"], "prompt.reviewer")
        self.assertEqual(save_response.json()["action"], "apply")


    def test_loadout_endpoint_rejects_unknown_action(self) -> None:
        characters = self.client.get('/api/v1/characters').json()["characters"]
        character_id = characters[0]["id"]

        save_response = self.client.post('/api/v1/characters/loadout', json={
            "character_id": character_id,
            "action": "ship-it",
            "loadout": {
                "prompt_profile": {"profile_id": "prompt.reviewer", "version": "2026-01"},
                "tool_loadout": {"loadout_id": "tools.review", "tool_ids": ["search"]},
                "doc_packs": [],
                "skills": [],
            },
        })

        self.assertEqual(save_response.status_code, 422)

    def test_loadout_endpoint_confirm_returns_confirm_action(self) -> None:
        characters = self.client.get('/api/v1/characters').json()["characters"]
        character_id = characters[0]["id"]

        save_response = self.client.post('/api/v1/characters/loadout', json={
            "character_id": character_id,
            "action": "confirm",
            "loadout": {
                "prompt_profile": {"profile_id": "prompt.reviewer", "version": "2026-01"},
                "tool_loadout": {"loadout_id": "tools.review", "tool_ids": ["search"]},
                "doc_packs": [],
                "skills": [],
            },
        })

        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(save_response.json()["action"], "confirm")


    def test_loadout_persists_across_registry_reinstantiation(self) -> None:
        payload = {
            "selected_character_id": "char-a",
            "profiles": [
                {
                    "id": "char-a",
                    "agent_id": "agent-a",
                    "display_name": "Alpha",
                    "class_name": "Wizard",
                    "level": 3,
                    "location": "Tower",
                    "current_action": "Idle",
                    "base_success_rate": "90%",
                    "loadout": {
                        "primary_weapon": "Staff",
                        "secondary_item": "Potion",
                        "armor": "Robe",
                        "hit_points": 92,
                        "mana": 70,
                    },
                }
            ],
        }
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        profile_path = Path(handle.name)
        profile_path.write_text(json.dumps(payload), encoding="utf-8")

        test_registry = CharacterRegistry(
            JsonCharacterProfileSource(profile_path),
            sink=JsonCharacterProfileSink(profile_path),
        )
        original_registry = gateway_runtime.character_registry
        gateway_runtime.character_registry = test_registry

        try:
            response = self.client.post('/api/v1/characters/loadout', json={
                "character_id": "char-a", "action": "apply",
                "loadout": {
                    "prompt_profile": {"profile_id": "prompt.survivor", "version": "v9"},
                    "tool_loadout": {"loadout_id": "tools.persist", "tool_ids": ["search"]},
                    "doc_packs": [{"pack_id": "docs.core", "version": "1"}],
                    "skills": [{"skill_id": "skill-creator", "enabled": True}],
                },
            })
            self.assertEqual(response.status_code, 200)

            restarted_registry = CharacterRegistry(
                JsonCharacterProfileSource(profile_path),
                sink=JsonCharacterProfileSink(profile_path),
            )
            self.assertEqual(restarted_registry.selected_character_id(), "char-a")
            self.assertEqual(
                restarted_registry.selected_character_loadout().prompt_profile.profile_id,
                "prompt.survivor",
            )
        finally:
            gateway_runtime.character_registry = original_registry

    def test_knowledge_node_documentation_endpoint_returns_not_found_for_unknown_node(self) -> None:
        docs_response = self.client.get('/api/v1/knowledge-tree/nodes/missing-node/documentation')
        self.assertEqual(docs_response.status_code, 404)
        payload = docs_response.json()
        self.assertIn("Unknown knowledge node id", payload["detail"])

    def test_game_state_party_uses_character_registry(self) -> None:
        state = fetch_game_state()
        party = state.get("party", [])
        profile_ids = {profile.agent_id for profile in character_registry.list_profiles()}
        party_ids = {member["id"] for member in party}
        self.assertEqual(profile_ids, party_ids)


if __name__ == '__main__':
    unittest.main()
