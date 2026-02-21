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

export interface DailyBudget {
  max: number;
  spent: number;
  unit: string;
}

export interface GameState {
  system_status: "OPERATIONAL" | "HALTED" | "DEGRADED";
  daily_budget: DailyBudget;
  party: Agent[];
  active_quests: Quest[];
  guardrail_log: GuardrailEntry[];
}

export interface GuardrailEntry {
  id: string;
  timestamp: string;
  blocked_command: string;
  reason: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
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
