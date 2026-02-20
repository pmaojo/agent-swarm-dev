# Agent Swarm Development System - Specification

## Overview

Sistema de desarrollo para crear infraestructura de agentes autónomo basado en Anthropic Swarm + Synapse.

## Tech Stack

- **Agentes**: Anthropic Swarm pattern
- **Memoria**: Synapse Core v0.8.5 (crates.io)
- **Storage**: Oxigraph (RDF triple store)
- **Embeddings**: FastEmbed local (BGE-small-ENV15)
- **Deployment**: Vercel
- **MCP**: Model Context Protocol

## Synapse Core v0.8.5

### Instalación

```bash
# Desde crates.io (recomendado)
cargo install synapse-core

# O desde repositorio
git clone https://github.com/pmaojo/synapse-engine.git
cd synapse-engine
cargo install --path crates/synapse-core
```

### Uso

```bash
# gRPC server
synapse

# MCP mode
synapse --mcp

# Con storage custom
GRAPH_STORAGE_PATH=/data/graphs synapse
```

### Python SDK

```bash
pip install synapse-sdk
```

## Componentes

| Agente | Rol |
|--------|-----|
| Orchestrator | Coordina flujo |
| Coder | Genera código |
| Memory | Memoria Synapse |
| Reviewer | Revisa calidad |
| Deployer | Vercel |

## GitHub Actions

Workflow compila con Ubuntu 24.04 (GLIBC 2.38) + descarga embeddings automáticamente.

## Estado

- [x] Sistema creado
- [x] Repo configurado
- [ ] Push a GitHub
