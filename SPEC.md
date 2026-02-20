# Agent Swarm Development System - Specification

## Overview

Sistema de desarrollo para crear infraestructura de agentes autónomo basado en la propuesta de Anthropic para swarms, con memoria persistente via Synapse.

## Tech Stack

- **Agentes**: Anthropic Swarm pattern
- **Memoria**: Synapse Core (crates.io o pmaojo/synapse-engine)
- **Storage**: Oxigraph (RDF triple store)
- **Embeddings**: FastEmbed local (BGE-small-ENV15)
- **Deployment**: Vercel
- **MCP**: Model Context Protocol

## Synapse Core

### Instalación

```bash
# Desde crates.io
cargo install synapse-core

# O desde repositorio
git clone https://github.com/pmaojo/synapse-engine.git
cd synapse-engine/crates/synapse-core
cargo install --path .
```

### Uso

```bash
# gRPC server (puerto 50051)
synapse

# MCP mode
synapse --mcp

# Con storage custom
GRAPH_STORAGE_PATH=/data/graphs synapse
```

### Python SDK

```bash
pip install synapse-sdk

from synapse import get_client
client = get_client()
client.ingest_triples([{"subject": "x", "predicate": "y", "object": "z"}])
```

## Componentes

### Agentes

1. **Orchestrator** - Coordina flujo (Anthropic Swarm)
2. **Coder** - Genera código
3. **Memory** - Memoria Synapse
4. **Reviewer** - Revisa calidad
5. **Deployer** - Despliega a Vercel

## Flujo

```
User → orchestrator → coder → reviewer → deployer → URL
         ↑                              ↓
         └──────── Memory (Synapse) ←──┘
```

## GitHub Actions

Workflow en `.github/workflows/ci.yml` compila Synapse con embeddings:

```yaml
runs-on: ubuntu-24.04  # GLIBC 2.38
features: local-embeddings
```

## Estado

- [x] Repositorio limpio (zeroclaw-neurosymbolic borrado)
- [x] Sistema configurado
- [ ] Testing
