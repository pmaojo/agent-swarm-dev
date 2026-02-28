<img width="1024" height="434" alt="agent-swarm-banner" src="https://github.com/user-attachments/assets/644269fd-bfe9-43ac-b909-4c3308ec96e3" />

# Agent Swarm Development System

A neuro-symbolic agent swarm with graph-driven orchestration using Synapse knowledge graphs. Features dual-mode operation: turn-based (game-like) or autonomous parallel execution.

## ✨ Key Features

| Feature                        | Description                                          |
| ------------------------------ | ---------------------------------------------------- |
| **Graph-Driven Orchestration** | State machine driven by Synapse RDF queries          |
| **Dual Modes**                 | Turn-based (Godot Visualizer) or Autonomous (Trello) |
| **MCP Integration**            | Native Model Context Protocol for all components     |
| **NIST Guardrails**            | Security compliance built into agent execution       |
| **Fog of War**                 | Agent visibility limited by explored knowledge       |
| **Economic Constraints**       | Daily budget tracking with HALT on overspend         |
| **CodeGraph Intelligence**     | Rust-based code parsing and graph analysis           |
| **API Sandbox**                | Apicentric integration for contract testing          |

## 🧠 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Request                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         Rust Gateway (swarmd) - Port 18789                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  POST /api/v1/control/commands                      │   │
│  │  GET  /api/v1/game-state                           │   │
│  │  WS   /api/v1/events/combat/stream                │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator Agent (Graph-Driven)                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. Query Synapse → Determine task type                │ │
│  │ 2. Find handler agent                                 │ │
│  │ 3. Execute agent → Collect result                     │ │
│  │ 4. Query graph → Determine next task                  │ │
│  │ 5. Repeat until terminal state                       │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Synapse Knowledge Graph                   │
│  • RDF Triples (Subject, Predicate, Object)                │
│  • SPARQL Queries for reasoning                            │
│  • Vector embeddings for semantic search                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent Swarm                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ProductMgr│ →Architect│ →  Coder  │ → Reviewer│ →Deployer│
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.10+
# Rust (for building swarmd)
# Docker (optional)
```

### 1. Start All Services

```bash
# The easiest way - starts Synapse, FastEmbed, and Gateway
./scripts/start_all.sh
```

Or manually:

```bash
# Terminal 1: Synapse (graph DB)
./synapse --mcp

# Terminal 2: FastEmbed (embeddings)
python scripts/embeddings_server.py --port 11434

# Terminal 3: Gateway (HTTP API)
cargo run -p swarmd
```

### 2. Run the Swarm

**Option A: Direct Task**

```bash
python3 scripts/swarm_flow.py "Create a REST API"
```

**Option B: Autonomous (Trello)**

```bash
python3 scripts/run_trello_bridge.py
```

**Option C: Via MCP**

```bash
# Configure in .mcp/config.json for Claude Code/Copilot
echo '{"method": "run_swarm", "params": {"task": "hello"}, "id": 1}' | python scripts/swarm_mcp.py
```

### 3. Access the Gateway

```bash
# Game state
curl http://localhost:18789/api/v1/game-state

# Knowledge graph
curl http://localhost:18789/api/v1/graph-nodes

# WebSocket combat stream
wscat -c ws://localhost:18789/api/v1/events/combat/stream
```

## 🎮 Dual Modes

### Mode 1: Turn-Based (Godot Visualizer)

Interactive game-like UI - send commands manually:

- `ASSIGN_MISSION` - Assign task to agent
- `PAUSE_AGENT` / `RESUME_AGENT` - Control agent state
- `PATCH_SERVICE` / `ROLLBACK_SERVICE` / `RESTART_SERVICE` - Service ops
- `ISOLATE_SERVICE` - Security isolation

Open `visualizer/project.godot` in Godot 4.x to play.

### Mode 2: Autonomous (Trello + OpenSpec)

Fully automated - agents process Trello cards:

| List         | Agent          | Action                      |
| ------------ | -------------- | --------------------------- |
| INBOX        | ProductManager | Ideas → OpenSpec            |
| REQUIREMENTS | Architect      | Spec → Design               |
| DESIGN       | Human          | Review & Approve            |
| TODO         | Orchestrator   | Coder → Reviewer → Deployer |

## 🤖 Agents

| Agent              | File                        | Capabilities                  |
| ------------------ | --------------------------- | ----------------------------- |
| **Orchestrator**   | `agents/orchestrator.py`    | Graph reasoning, task routing |
| **ProductManager** | `agents/product_manager.py` | OpenSpec generation           |
| **Architect**      | `agents/architect.py`       | Technical design              |
| **Coder**          | `agents/coder.py`           | Code gen with tools           |
| **Reviewer**       | `agents/reviewer.py`        | Linting, contract testing     |
| **Deployer**       | `agents/deployer.py`        | Vercel/Docker deployment      |
| **Memory**         | `agents/memory.py`          | Synapse memory ops            |
| **Analyst**        | `agents/analyst.py`         | Pattern analysis              |

### Coder Tools

```python
read_file, write_file, patch_file, list_dir
read_logs, execute_command (NIST-guarded)
search_documentation, read_url
```

## 🔌 MCP Integration

Configured in [`.mcp/config.json`](.mcp/config.json):

```json
{
  "mcpServers": {
    "synapse": { "command": "synapse", "args": ["--mcp"] },
    "swarm": { "command": "python3", "args": ["scripts/swarm_mcp.py"] },
    "apicentric": {
      "command": "./apicentric_repo/target/release/apicentric",
      "args": ["mcp"]
    }
  }
}
```

### Available MCP Tools

- `run_swarm(task)` - Execute full workflow
- `run_agent(agent, task)` - Run single agent
- `query_memory(sparql)` - Query Synapse
- `create_service`, `start_service`, `stop_service` - Apicentric

## 🐳 Docker Deployment

```bash
# Build
docker build -t agent-swarm-gateway:local -f Dockerfile.rust-gateway .

# Run
docker run --rm -p 18789:18789 \
  -e SYNAPSE_GRPC_HOST=synapse \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  agent-swarm-gateway:local

# Health check
curl http://localhost:18789/api/v1/game-state
```

Or use docker-compose:

```bash
docker-compose up -d
```

## 🧪 Testing

```bash
# Test graph reasoning
python3 scripts/test_flow.py

# Test embeddings
python3 scripts/test_embeddings.py

# Test Synapse connection
python3 scripts/simple_synapse_client.py

# Run MCP server
python3 scripts/swarm_mcp.py
```

## ⚙️ Configuration

### Environment Variables

| Variable             | Default     | Description         |
| -------------------- | ----------- | ------------------- |
| `LLM_MODEL`          | `gpt-4`     | Model for agents    |
| `OPENAI_API_KEY`     | -           | OpenAI API key      |
| `SYNAPSE_GRPC_HOST`  | `localhost` | Synapse host        |
| `SYNAPSE_GRPC_PORT`  | `50051`     | Synapse port        |
| `GATEWAY_PORT`       | `18789`     | HTTP gateway port   |
| `EMBEDDING_PROVIDER` | `local`     | `local` or `remote` |

### Trello Integration

```bash
export TRELLO_API_KEY=xxx
export TRELLO_TOKEN=xxx
export TRELLO_BOARD_ID=xxx
```

### Telegram Alerts

```bash
export TELEGRAM_BOT_TOKEN=xxx
export TELEGRAM_CHAT_ID=xxx
```

## 📦 Components

| Component      | Location               | Description         |
| -------------- | ---------------------- | ------------------- |
| **swarmd**     | `swarmd/src/`          | Rust gateway (Axum) |
| **Synapse**    | `./synapse`            | Graph DB binary     |
| **Apicentric** | `apicentric_repo/`     | API simulator       |
| **Visualizer** | `visualizer/`          | Godot game          |
| **Dashboard**  | `commander-dashboard/` | React web UI        |

## 🔧 Development

### Adding New Agents

1. Add to `swarm_schema.yaml`:

```yaml
agents:
  YourAgent:
    description: "Your agent"
    seat_index: 5

tasks:
  YourTask:
    handler: YourAgent
```

2. Implement in `agents/your_agent.py`:

```python
class YourAgent:
    def run(self, task: str, context: dict) -> dict:
        return {"status": "success"}
```

### Building from Source

```bash
# Rust gateway
cd swarmd && cargo build --release

# Synapse (light mode)
cd synapse-engine
cargo build --release --no-default-features -p synapse-core

# Start
./target/release/synapse --mcp
```

## 📊 Monitoring

### Logs

```bash
# Gateway logs
tail -f swarmd.log

# Synapse logs
tail -f synapse.log
```

### Web UI

- Gateway: http://localhost:18789
- Dashboard: http://localhost:3000 (if running)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests in `tests/`
4. Update `swarm_schema.yaml` for new agents
5. Submit a pull request

## 📄 License

MIT

## 🙏 Acknowledgments

- [Synapse](https://github.com/synapse-engine) - Neuro-symbolic knowledge graph
- [FastEmbed](https://github.com/AnswerDotAI/fastembed) - Vector embeddings
- [Ratatui](https://github.com/ratatui-org/ratatui) - Rust TUI
- [Apicentric](https://github.com/pmaojo/apicentric) - API contract testing

---

**Last Updated:** 2026-02-28
**Version:** 1.4
