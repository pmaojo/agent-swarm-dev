from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


API_V1_PREFIX = "/api/v1"


class SystemStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    OUTAGE = "OUTAGE"
    UNKNOWN = "UNKNOWN"


class QuestStatus(str, Enum):
    REQUIREMENTS = "REQUIREMENTS"
    DESIGN = "DESIGN"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class DailyBudget(BaseModel):
    max: float
    spent: float
    unit: str = "USD"


class PartyStats(BaseModel):
    hp: int
    mana: int
    success_rate: str


class PartyMember(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    class_name: str = Field(alias="class")
    level: int
    stats: PartyStats
    current_action: str
    location: str


class CharacterLoadout(BaseModel):
    primary_weapon: str
    secondary_item: str
    armor: str
    hit_points: int = Field(ge=0)
    mana: int = Field(ge=0)


class CharacterProfile(BaseModel):
    id: str
    agent_id: str
    display_name: str
    class_name: str
    level: int = Field(ge=1)
    location: str
    current_action: str = "Idle"
    base_success_rate: str = "95%"
    loadout: CharacterLoadout


class ActiveQuest(BaseModel):
    id: str
    title: str
    status: QuestStatus


class RepositoryState(BaseModel):
    id: str
    name: str
    swarm: List[str] = Field(default_factory=list)


class ServiceHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    HALTED = "halted"
    UNDER_ATTACK = "under_attack"


class ServiceState(BaseModel):
    id: str
    name: str
    health: ServiceHealth
    hp: int = 100
    latency_ms: float = 0.0
    error_rate: float = 0.0


class CountryState(BaseModel):
    id: str
    name: str
    services: List[ServiceState] = Field(default_factory=list)


class GameState(BaseModel):
    system_status: SystemStatus
    daily_budget: DailyBudget
    party: List[PartyMember] = Field(default_factory=list)
    active_quests: List[ActiveQuest] = Field(default_factory=list)
    fog_map: Dict[str, Any] = Field(default_factory=dict)
    repositories: List[RepositoryState] = Field(default_factory=list)
    countries: List[CountryState] = Field(default_factory=list)
    knowledge_tree: List["KnowledgeNode"] = Field(default_factory=list)


class KnowledgeNodeCost(BaseModel):
    budget: float
    time_hours: int


class KnowledgeNode(BaseModel):
    id: str
    domain: str
    name: str
    capability: str
    level: int
    prerequisites: List[str] = Field(default_factory=list)
    cost: KnowledgeNodeCost
    unlocked: bool = False
    source_type: str = "seed"
    source_ref: str = "seed://default"
    documentation: str = ""


class GraphNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    label: str
    node_type: str = Field(alias="type")


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphData(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class ControlCommandType(str, Enum):
    ASSIGN_MISSION = "ASSIGN_MISSION"
    PAUSE_AGENT = "PAUSE_AGENT"
    RESUME_AGENT = "RESUME_AGENT"
    REFRESH_GRAPH = "REFRESH_GRAPH"
    PATCH_SERVICE = "PATCH_SERVICE"
    ROLLBACK_SERVICE = "ROLLBACK_SERVICE"
    RESTART_SERVICE = "RESTART_SERVICE"
    ISOLATE_SERVICE = "ISOLATE_SERVICE"
    CONFIGURE_CHARACTER_LOADOUT = "CONFIGURE_CHARACTER_LOADOUT"


class PromptProfileRef(BaseModel):
    profile_id: str
    version: Optional[str] = None


class ToolLoadout(BaseModel):
    loadout_id: Optional[str] = None
    tool_ids: List[str] = Field(default_factory=list)


class DocPackRef(BaseModel):
    pack_id: str
    version: Optional[str] = None


class SkillSelection(BaseModel):
    skill_id: str
    enabled: bool = True


class CharacterLoadoutSelection(BaseModel):
    prompt_profile: Optional[PromptProfileRef] = None
    tool_loadout: Optional[ToolLoadout] = None
    doc_packs: List[DocPackRef] = Field(default_factory=list)
    skills: List[SkillSelection] = Field(default_factory=list)


class ControlCommand(BaseModel):
    command: ControlCommandType
    payload_version: Optional[str] = None
    agent_id: Optional[str] = None
    repo_id: Optional[str] = None
    task: Optional[str] = None
    loadout: Optional[CharacterLoadoutSelection] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ControlCommandAck(BaseModel):
    status: str = "accepted"
    command: ControlCommand


class EventType(str, Enum):
    MISSION_ASSIGNED = "MISSION_ASSIGNED"
    HARDENING_EVENT = "HARDENING_EVENT"
    BUG_SPAWNED = "BUG_SPAWNED"
    SERVICE_DAMAGED = "SERVICE_DAMAGED"
    SERVICE_RECOVERED = "SERVICE_RECOVERED"


class GatewayEvent(BaseModel):
    type: EventType
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "INFO"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EventAck(BaseModel):
    status: str = "broadcasted"
    event: GatewayEvent
