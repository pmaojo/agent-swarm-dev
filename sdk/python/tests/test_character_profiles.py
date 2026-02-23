import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.character_profiles import CharacterRegistry, JsonCharacterProfileSource


class CharacterProfileRegistryTests(unittest.TestCase):
    def _build_temp_profile_file(self) -> Path:
        payload = {
            "selected_character_id": "char-b",
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
                },
                {
                    "id": "char-b",
                    "agent_id": "agent-b",
                    "display_name": "Beta",
                    "class_name": "Rogue",
                    "level": 4,
                    "location": "Gate",
                    "current_action": "Scout",
                    "base_success_rate": "93%",
                    "loadout": {
                        "primary_weapon": "Daggers",
                        "secondary_item": "Bomb",
                        "armor": "Leather",
                        "hit_points": 88,
                        "mana": 55,
                    },
                },
            ],
        }
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        Path(handle.name).write_text(json.dumps(payload), encoding="utf-8")
        return Path(handle.name)

    def test_registry_uses_selected_character_id_from_source(self) -> None:
        source = JsonCharacterProfileSource(self._build_temp_profile_file())
        registry = CharacterRegistry(source)

        self.assertEqual(registry.selected_character_id(), "char-b")
        self.assertEqual(len(registry.list_profiles()), 2)

    def test_select_character_raises_for_unknown_id(self) -> None:
        source = JsonCharacterProfileSource(self._build_temp_profile_file())
        registry = CharacterRegistry(source)

        with self.assertRaises(KeyError):
            registry.select_character("char-missing")


if __name__ == "__main__":
    unittest.main()
