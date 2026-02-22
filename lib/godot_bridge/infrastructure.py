from __future__ import annotations

from pathlib import Path

from lib.godot_bridge.domain import GodotProjectBlueprint


class FileSystemProjectWriter:
    def write(self, base_path: Path, blueprint: GodotProjectBlueprint) -> None:
        for artifact in blueprint.all_artifacts:
            output_path = base_path / artifact.relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(artifact.content, encoding="utf-8")
