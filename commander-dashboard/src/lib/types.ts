export type AgentClass = "Bard" | "Wizard" | "Warrior" | "Paladin";

export interface Agent {
  id: string;
  name: string;
  class: AgentClass;
  stats: {
    hp: number;
    mana: number;
    success_rate: string;
  };
  current_action: string;
  location: string;
}

export interface Quest {
  id: string;
  title: string;
  stage: "Requirements" | "Design" | "Todo" | "In Progress";
  difficulty: "Easy" | "Medium" | "Hard" | "Legendary";
  assigned_agent?: string;
}

export interface Repository {
  id: string;
  name: string;
  path?: string;
  tasks_pending?: number;
  status?: "ok" | "error";
  size?: number;
  swarm?: string[];
}

export interface DailyBudget {
  max: number;
  spent: number;
  unit: string;
}

export interface GuardrailEntry {
  id: string;
  timestamp: string;
  blocked_command: string;
  reason: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
}

export interface SovereignControlStatus {
  approved: boolean;
  approved_by?: string;
  policy_id: string;
}

export interface GameState {
  system_status: "OPERATIONAL" | "HALTED" | "DEGRADED" | "OUTAGE";
  daily_budget: DailyBudget;
  party: Agent[];
  active_quests: Quest[];
  repositories: Repository[];
  guardrail_log?: GuardrailEntry[];
  knowledge_tree: KnowledgeNode[];
  sovereign_controls?: SovereignControlStatus;
}

export interface GraphNode {
  data: {
    id: string;
    label: string;
    type: string;
    active?: boolean;
    triples?: { subject: string; predicate: string; object: string }[];
  };
}

export interface GraphEdge {
  data: {
    id: string;
    source: string;
    target: string;
    label?: string;
  };
}

export interface GraphData {
  elements: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
}

export interface KnowledgeNodeCost {
  budget: number;
  time_hours: number;
}

export interface KnowledgeNode {
  id: string;
  domain: string;
  name: string;
  capability: string;
  level: number;
  prerequisites: string[];
  cost: KnowledgeNodeCost;
  unlocked: boolean;
}

export type ControlCommandType =
  | "ASSIGN_MISSION"
  | "HALT"
  | "RESUME"
  | "SET_AGENT_PRIORITY"
  | "DEPLOY"
  | "ROLLBACK"
  | "CONFIGURE_AGENT_MODEL";

export interface LlmProfile {
  provider: string;
  model: string;
  hierarchy: "champion" | "captain" | "specialist" | "minion";
}

export interface SovereignCommand {
  command: ControlCommandType;
  actor: string;
  agent_id?: string;
  repo_id?: string;
  task?: string;
  mission_id?: string;
  priority?: number;
  deployment_target?: string;
  rollback_to?: string;
  llm_profile?: LlmProfile;
  nist_policy_id: string;
  approved_by?: string;
  metadata?: Record<string, string>;
}

export interface CommandAck {
  tracking_id: string;
  status: "SENT" | "ACCEPTED" | "REJECTED" | "COMPLETED";
  reason?: string;
  final_state?: string;
  command: SovereignCommand;
}

export interface AuditRecord {
  tracking_id: string;
  actor: string;
  command: string;
  phase: "SENT" | "ACCEPTED" | "REJECTED" | "COMPLETED";
  timestamp: string;
  policy_id: string;
  approved_by?: string;
  details: string;
}
