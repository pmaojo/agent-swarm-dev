from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lib.godot_bridge.domain import GodotProjectBlueprint


class ProjectWriter(Protocol):
    def write(self, base_path: Path, blueprint: GodotProjectBlueprint) -> None:
        ...


class MaterializeGodotProjectUseCase:
    def __init__(self, writer: ProjectWriter) -> None:
        self._writer = writer

    def execute(self, destination_root: Path, blueprint: GodotProjectBlueprint) -> None:
        self._writer.write(destination_root, blueprint)
