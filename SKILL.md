---
name: agent-swarm-dev
description: Sistema de desarrollo para agent swarms con Synapse memory. Usa Anthropic Swarm pattern + Synapse (pmaojo/synapse-engine) para memoria persistente. Flujo: SPEC.md → agentes especializados → código → Vercel.
---

# Agent Swarm Development System

Sistema de desarrollo para crear infraestructura de agentes usando:
- **Anthropic Swarm**: Patrón de orquestación de agentes
- **Synapse**: Memoria neuro-simbólica (pmaojo/synapse-engine)
- **MCP**: Model Context Protocol para herramientas
- **Vercel**: Despliegue

## Estructura

```
agent-swarm-dev/
├── SKILL.md              # Esta skill
├── SPEC.md               # Especificación del sistema
├── agents/               # Agentes especializados
│   ├── orchestrator.md   # Coordina flujo (Anthropic Swarm)
│   ├── coder.md         # Genera código
│   ├── memory.md         # Memoria Synapse
│   └── reviewer.md       # Revisa calidad
├── scripts/
│   ├── init_swarm.sh     # Iniciar proyecto
│   ├── run_agent.sh      # Ejecutar agente
│   ├── deploy.sh         # Desplegar a Vercel
│   ├── synapse_agent.py  # Tool Python SDK
│   └── synapse_mcp.py    # Servidor MCP
├── .mcp/
│   └── config.json       # Configuración MCP
└── deploy/
    └── vercel.json       # Config Vercel
```

## Uso

### 1. Iniciar Proyecto
```bash
./scripts/init_swarm.sh mi-proyecto
```

### 2. Ejecutar Agente
```bash
./scripts/run_agent.sh orchestrator "Crear una API REST"
```

### 3. Desplegar
```bash
./scripts/deploy.sh
```

## MCP Tools (Synapse)

| Tool | Descripción |
|------|-------------|
| `query_graph` | Consulta todos los triples |
| `ingest_triple` | Añade un triple |
| `query_sparql` | Consulta SPARQL |
| `add_observation` | Añade observación |
| `ingest_memory` | Ingesta múltiples triples |

## Flujo Swarm

```
User → orchestrator → (handoff) → coder → (handoff) → reviewer → (handoff) → deployer → URL
         ↑                                      ↓
         └────────── Memory (Synapse) ←────────┘
```

## Spec-Driven Development (GSD + OpenSpec)

Two frameworks for spec-driven development are integrated:

### GSD (Get Shit Done)
```bash
npx get-shit-done-cc@latest --claude --global
```
- `/gsd:spec` - Generate SPEC.md
- `/gsd:build` - Execute build
- `/gsd:test` - Run tests
- `/gsd:verify` - Verify implementation

### OpenSpec (@fission-ai/openspec)
```bash
npm install -g @fission-ai/openspec@latest
```
- `/opsx:new <feature>` - Create new feature
- `/opsx:ff` - Generate full planning docs
- `/opsx:apply` - Implement tasks
- `/opsx:archive` - Archive completed

Both work with Claude Code, OpenCode, and OpenClaw via MCP.

## Synapse Integration

### Python SDK
```python
from synapse import get_client
client = get_client()
client.ingest_triples([{"subject": "agent_1", "predicate": "completed", "object": "task_123"}])
```

### MCP
El servidor MCP (`synapse_mcp.py`) expone las tools via JSON-RPC stdio.

## GSD Integration (Get Shit Done)

Sistema de context engineering y spec-driven development. Útil para estructurar tareas complejas.

### Comandos GSD
- `/gsd:spec` - Generar SPEC.md desde description
- `/gsd:build` - Ejecutar build completo
- `/gsd:test` - Ejecutar tests
- `/gsd:verify` - Verificar implementación vs spec

### Flujo GSD
1. **Describe** lo que quieres construir
2. GSD extrae contexto y genera spec
3. Claude Code ejecuta y verifica
4. Iterar hasta correcto

### Install
```bash
npx get-shit-done-cc@latest --claude --global
```

## namespaces

- `swarm`: Memoria del swarm
- `agents`: Estado de agentes
- `tasks`: Tareas y resultados
