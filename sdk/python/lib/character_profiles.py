from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from lib.contracts import CharacterProfile, PartyMember, PartyStats


class CharacterProfileDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_character_id: Optional[str] = None
    profiles: List[CharacterProfile] = Field(default_factory=list)


class CharacterProfileSource(Protocol):
    """Hexagonal input port for character profile loading."""

    def load_document(self) -> CharacterProfileDocument:
        ...


class JsonCharacterProfileSource:
    """JSON-backed adapter for character profiles."""

    def __init__(self, source_path: Path):
        self._source_path = source_path

    @property
    def source_path(self) -> Path:
        return self._source_path

    def load_document(self) -> CharacterProfileDocument:
        payload = json.loads(self._source_path.read_text(encoding="utf-8"))
        return CharacterProfileDocument.model_validate(payload)


class CharacterRegistry:
    """Application service for profile lifecycle and active selection."""

    def __init__(self, source: CharacterProfileSource):
        self._source = source
        document = source.load_document()
        self._profiles: List[CharacterProfile] = document.profiles

        first_profile_id = self._profiles[0].id if self._profiles else None
        if document.selected_character_id and self.get_profile(document.selected_character_id) is not None:
            self._selected_character_id: Optional[str] = document.selected_character_id
        else:
            self._selected_character_id = first_profile_id

    def list_profiles(self) -> List[CharacterProfile]:
        return list(self._profiles)

    def selected_character_id(self) -> Optional[str]:
        return self._selected_character_id

    def select_character(self, character_id: str) -> CharacterProfile:
        profile = self.get_profile(character_id)
        if profile is None:
            raise KeyError(character_id)
        self._selected_character_id = profile.id
        return profile

    def get_profile(self, character_id: str) -> Optional[CharacterProfile]:
        for profile in self._profiles:
            if profile.id == character_id:
                return profile
        return None

    def as_party_members(self) -> List[PartyMember]:
        return [
            PartyMember(
                id=profile.agent_id,
                name=profile.display_name,
                **{"class": profile.class_name},
                level=profile.level,
                stats=PartyStats(
                    hp=profile.loadout.hit_points,
                    mana=profile.loadout.mana,
                    success_rate=profile.base_success_rate,
                ),
                current_action=profile.current_action,
                location=profile.location,
            )
            for profile in self._profiles
        ]
