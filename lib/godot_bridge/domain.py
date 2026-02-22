from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lib.godot_bridge.templates import (
    AGENT_UNIT_GD,
    BRIDGE_GD,
    BUILDING_GD,
    CITADEL_MANAGER_GD,
    FOG_MANAGER_GD,
)


@dataclass(frozen=True)
class GeneratedArtifact:
    relative_path: Path
    content: str


@dataclass(frozen=True)
class GodotProjectBlueprint:
    scripts: tuple[GeneratedArtifact, ...]
    scenes: tuple[GeneratedArtifact, ...]

    @property
    def all_artifacts(self) -> tuple[GeneratedArtifact, ...]:
        return self.scripts + self.scenes


def _scene_template(script_filename: str, root_type: str) -> str:
    return (
        '[gd_scene load_steps=2 format=3]\n\n'
        f'[ext_resource type="Script" path="res://scripts/{script_filename}" id="1"]\n\n'
        f'[node name="{Path(script_filename).stem.title().replace("_", "")}" type="{root_type}"]\n'
        'script = ExtResource("1")\n'
    )


def build_default_blueprint() -> GodotProjectBlueprint:
    script_artifacts = (
        GeneratedArtifact(Path("visualizer/scripts/agent_unit.gd"), AGENT_UNIT_GD.strip() + "\n"),
        GeneratedArtifact(Path("visualizer/scripts/fog_manager.gd"), FOG_MANAGER_GD.strip() + "\n"),
        GeneratedArtifact(Path("visualizer/scripts/bridge.gd"), BRIDGE_GD.strip() + "\n"),
        GeneratedArtifact(Path("visualizer/scripts/citadel_manager.gd"), CITADEL_MANAGER_GD.strip() + "\n"),
        GeneratedArtifact(Path("visualizer/scripts/building.gd"), BUILDING_GD.strip() + "\n"),
    )

    scene_artifacts = (
        GeneratedArtifact(
            Path("visualizer/scenes/agent_unit.tscn"),
            _scene_template("agent_unit.gd", "CharacterBody2D"),
        ),
        GeneratedArtifact(
            Path("visualizer/scenes/fog_manager.tscn"),
            _scene_template("fog_manager.gd", "Node2D"),
        ),
        GeneratedArtifact(
            Path("visualizer/scenes/bridge.tscn"),
            _scene_template("bridge.gd", "Node"),
        ),
        GeneratedArtifact(
            Path("visualizer/scenes/citadel_manager.tscn"),
            _scene_template("citadel_manager.gd", "Node"),
        ),
        GeneratedArtifact(
            Path("visualizer/scenes/building.tscn"),
            _scene_template("building.gd", "Spatial"),
        ),
    )

    return GodotProjectBlueprint(scripts=script_artifacts, scenes=scene_artifacts)
