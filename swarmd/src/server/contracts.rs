use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SystemStatus {
    Operational,
    Degraded,
    Outage,
    Halted,
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

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ServiceState {
    pub id: String,
    pub name: String,
    pub health: ServiceHealth,
    #[serde(default = "default_service_hp")]
    pub hp: i32,
    #[serde(default)]
    pub latency_ms: f64,
    #[serde(default)]
    pub error_rate: f64,
}

const fn default_service_hp() -> i32 {
    100
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CountryState {
    pub id: String,
    pub name: String,
    pub services: Vec<ServiceState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KnowledgeNodeCost {
    pub budget: f64,
    pub time_hours: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KnowledgeNode {
    pub id: String,
    pub domain: String,
    pub name: String,
    pub capability: String,
    pub level: i32,
    pub prerequisites: Vec<String>,
    pub cost: KnowledgeNodeCost,
    pub unlocked: bool,
    #[serde(default = "default_knowledge_source_type")]
    pub source_type: String,
    #[serde(default = "default_knowledge_source_ref")]
    pub source_ref: String,
    #[serde(default)]
    pub documentation: String,
}

fn default_knowledge_source_type() -> String {
    "seed".to_string()
}

fn default_knowledge_source_ref() -> String {
    "seed://default".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PolicyApprovalStatus {
    pub approved: bool,
    pub approved_by: Option<String>,
    pub policy_id: String,
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
    pub knowledge_tree: Vec<KnowledgeNode>,
    pub sovereign_controls: PolicyApprovalStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphNodeData {
    pub id: String,
    pub label: String,
    #[serde(rename = "type")]
    pub node_type: String,
    pub active: bool,
    #[serde(default)]
    pub triples: Vec<GraphTriple>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphTriple {
    pub subject: String,
    pub predicate: String,
    pub object: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphNode {
    pub data: GraphNodeData,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphEdgeData {
    pub id: String,
    pub source: String,
    pub target: String,
    pub label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GraphEdge {
    pub data: GraphEdgeData,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct GraphElements {
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<GraphEdge>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct GraphData {
    pub elements: GraphElements,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ControlCommandType {
    AssignMission,
    PauseAgent,
    ResumeAgent,
    RefreshGraph,
    #[serde(alias = "ISOLATE_SERVICE")]
    Halt,
    #[serde(alias = "RESTART_SERVICE")]
    Resume,
    SetAgentPriority,
    #[serde(alias = "PATCH_SERVICE")]
    Deploy,
    #[serde(alias = "ROLLBACK_SERVICE")]
    Rollback,
    ConfigureAgentModel,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LlmProfile {
    pub provider: String,
    pub model: String,
    pub hierarchy: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlCommand {
    pub command: ControlCommandType,
    pub actor: String,
    pub agent_id: Option<String>,
    pub repo_id: Option<String>,
    pub task: Option<String>,
    pub mission_id: Option<String>,
    pub priority: Option<u8>,
    pub deployment_target: Option<String>,
    pub rollback_to: Option<String>,
    pub llm_profile: Option<LlmProfile>,
    pub nist_policy_id: String,
    pub approved_by: Option<String>,
    #[serde(default)]
    pub metadata: std::collections::HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CommandPhase {
    Sent,
    Accepted,
    Rejected,
    Completed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlCommandAck {
    pub tracking_id: String,
    pub status: CommandPhase,
    pub reason: Option<String>,
    pub final_state: Option<String>,
    pub command: ControlCommand,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuditRecord {
    pub tracking_id: String,
    pub actor: String,
    pub command: ControlCommandType,
    pub phase: CommandPhase,
    pub timestamp: String,
    pub policy_id: String,
    pub approved_by: Option<String>,
    pub details: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EventType {
    MissionAssigned,
    HardeningEvent,
    BugSpawned,
    ServiceDamaged,
    ServiceRecovered,
    JulesCloudBuilding,
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


#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KnowledgeNodeDocumentationResponse {
    pub node_id: String,
    pub documentation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KnowledgeNodeIngestRequest {
    pub node_id: String,
    pub domain: String,
    pub name: String,
    pub capability: String,
    pub level: i32,
    pub budget_cost: f64,
    pub time_cost_hours: i32,
    #[serde(default)]
    pub prerequisites: Vec<String>,
    #[serde(default)]
    pub docs_text: String,
    #[serde(default = "default_source_type")]
    pub source_type: String,
    #[serde(default = "default_source_ref")]
    pub source_ref: String,
}

fn default_source_type() -> String {
    "custom".to_string()
}

fn default_source_ref() -> String {
    "game://manual".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct IngestKnowledgeNodeResponse {
    pub status: String,
    pub node: KnowledgeNode,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MissionAssignment {
    pub agent_id: String,
    pub repo_id: String,
    pub task: String,
}
