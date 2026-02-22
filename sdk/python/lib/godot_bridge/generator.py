from __future__ import annotations

from pathlib import Path

from lib.godot_bridge.application import MaterializeGodotProjectUseCase
from lib.godot_bridge.domain import build_default_blueprint
from lib.godot_bridge.infrastructure import FileSystemProjectWriter


def materialize_godot_project(destination_root: Path) -> None:
    use_case = MaterializeGodotProjectUseCase(writer=FileSystemProjectWriter())
    blueprint = build_default_blueprint()
    use_case.execute(destination_root=destination_root, blueprint=blueprint)
