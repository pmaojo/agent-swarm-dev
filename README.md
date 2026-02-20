<img width="1024" height="572" alt="image_00b13d08-0cb7-44be-ac9b-1f37b30b2d9a" src="https://github.com/user-attachments/assets/63f9fe0b-44b7-49f4-8f5c-bd11c61edd1e" />

# Agent Swarm Development System

A spec-driven development system with neuro-symbolic memory using Synapse.

## Overview

Build autonomous agent swarms with:
- **Anthropic Swarm** pattern for orchestration
- **Synapse** for persistent RDF triple memory
- **FastEmbed** for vector embeddings
- **GSD** for context engineering

## Quick Start

### 1. Install Dependencies

```bash
# Python dependencies
pip install fastembed flask grpcio-tools synapse-sdk

# Synapse binary (light mode)
# Download from https://github.com/pmaojo/synapse-engine/releases
```

### 2. Start Services

```bash
# Terminal 1: Start FastEmbed server
python scripts/embeddings_server.py --port 11434

# Terminal 2: Start Synapse (light mode - RAM + remote embeddings)
./synapse
```

### 3. Run Agent

```bash
./scripts/run_agent.sh orchestrator "Create a REST API"
```

## Architecture

```
User → Orchestrator → Coder → Reviewer → Deployer
                ↓
           Synapse (Memory)
                ↓
         FastEmbed (Embeddings)
```

## Components

| Component | Description |
|-----------|-------------|
| `synapse` | Graph DB (RDF triples) |
| `embeddings_server.py` | FastEmbed HTTP API |
| `agents/` | Agent prompts |
| `scripts/` | Utility scripts |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `local` | Use `remote` for FastEmbed |
| `EMBEDDING_API_URL` | `http://localhost:11434/api/embeddings` | Embeddings endpoint |

### Synapse (Light Mode)

```bash
# Build light mode
cargo build --release --no-default-features -p synapse-core

# Run with remote embeddings
EMBEDDING_PROVIDER=remote ./target/release/synapse
```

## License

MIT
