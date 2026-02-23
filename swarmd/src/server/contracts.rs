use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SystemStatus {
    Operational,
    Degraded,
    Outage,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum QuestStatus {
    Requirements,
    Design,
    Ready,
    InProgress,
    Done,
    Blocked,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DailyBudget {
    pub max: f64,
    pub spent: f64,
    pub unit: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PartyStats {
    pub hp: i32,
    pub mana: i32,
    pub success_rate: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PartyMember {
    pub id: String,
    pub name: String,
    #[serde(rename = "class")]
    pub class_name: String,
    pub level: i32,
    pub stats: PartyStats,
    pub current_action: String,
    pub location: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActiveQuest {
    pub id: String,
    pub title: String,
    pub status: QuestStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RepositoryState {
    pub id: String,
    pub name: String,
    pub swarm: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ServiceHealth {
    Healthy,
    Degraded,
    Halted,
    UnderAttack,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ServiceState {
    pub id: String,
    pub name: String,
    pub health: ServiceHealth,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CountryState {
    pub id: String,
    pub name: String,
    pub services: Vec<ServiceState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GameState {
    pub system_status: SystemStatus,
    pub daily_budget: DailyBudget,
    pub party: Vec<PartyMember>,
    pub active_quests: Vec<ActiveQuest>,
    pub fog_map: serde_json::Value,
    pub repositories: Vec<RepositoryState>,
    pub countries: Vec<CountryState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphNode {
    pub id: String,
    pub label: String,
    #[serde(rename = "type")]
    pub node_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphEdge {
    pub source: String,
    pub target: String,
    pub label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct GraphData {
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<GraphEdge>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ControlCommandType {
    AssignMission,
    PauseAgent,
    ResumeAgent,
    RefreshGraph,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlCommand {
    pub command: ControlCommandType,
    pub agent_id: Option<String>,
    pub repo_id: Option<String>,
    pub task: Option<String>,
    #[serde(default)]
    pub metadata: std::collections::HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlCommandAck {
    pub status: String,
    pub command: ControlCommand,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EventType {
    MissionAssigned,
    HardeningEvent,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GatewayEvent {
    pub r#type: EventType,
    pub message: String,
    #[serde(default)]
    pub details: std::collections::HashMap<String, String>,
    pub severity: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EventAck {
    pub status: String,
    pub event: GatewayEvent,
}
