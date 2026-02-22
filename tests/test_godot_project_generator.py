import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.godot_bridge.generator import materialize_godot_project


def test_materialize_godot_project_creates_expected_files(tmp_path: Path) -> None:
    materialize_godot_project(tmp_path)

    expected_scripts = {
        "agent_unit.gd",
        "fog_manager.gd",
        "bridge.gd",
        "citadel_manager.gd",
        "building.gd",
    }
    expected_scenes = {
        "agent_unit.tscn",
        "fog_manager.tscn",
        "bridge.tscn",
        "citadel_manager.tscn",
        "building.tscn",
    }

    scripts_dir = tmp_path / "visualizer" / "scripts"
    scenes_dir = tmp_path / "visualizer" / "scenes"

    assert {path.name for path in scripts_dir.iterdir()} == expected_scripts
    assert {path.name for path in scenes_dir.iterdir()} == expected_scenes


def test_materialize_godot_project_writes_minimum_expected_content(tmp_path: Path) -> None:
    materialize_godot_project(tmp_path)

    bridge_script = (tmp_path / "visualizer" / "scripts" / "bridge.gd").read_text(encoding="utf-8")
    assert "extends Node" in bridge_script
    assert "signal game_state_updated(state)" in bridge_script

    bridge_scene = (tmp_path / "visualizer" / "scenes" / "bridge.tscn").read_text(encoding="utf-8")
    assert "[ext_resource type=\"Script\" path=\"res://scripts/bridge.gd\" id=\"1\"]" in bridge_scene
    assert 'script = ExtResource("1")' in bridge_scene


def test_materialize_godot_project_is_idempotent(tmp_path: Path) -> None:
    materialize_godot_project(tmp_path)

    first_snapshot = {
        path.relative_to(tmp_path).as_posix(): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    materialize_godot_project(tmp_path)

    second_snapshot = {
        path.relative_to(tmp_path).as_posix(): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert first_snapshot == second_snapshot
