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


class ActiveQuest(BaseModel):
    id: str
    title: str
    status: QuestStatus


class RepositoryState(BaseModel):
    id: str
    name: str
    swarm: List[str] = Field(default_factory=list)


class GameState(BaseModel):
    system_status: SystemStatus
    daily_budget: DailyBudget
    party: List[PartyMember] = Field(default_factory=list)
    active_quests: List[ActiveQuest] = Field(default_factory=list)
    fog_map: Dict[str, Any] = Field(default_factory=dict)
    repositories: List[RepositoryState] = Field(default_factory=list)


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


class ControlCommand(BaseModel):
    command: ControlCommandType
    agent_id: Optional[str] = None
    repo_id: Optional[str] = None
    task: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ControlCommandAck(BaseModel):
    status: str = "accepted"
    command: ControlCommand


class EventType(str, Enum):
    MISSION_ASSIGNED = "MISSION_ASSIGNED"
    HARDENING_EVENT = "HARDENING_EVENT"


class GatewayEvent(BaseModel):
    type: EventType
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "INFO"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EventAck(BaseModel):
    status: str = "broadcasted"
    event: GatewayEvent
