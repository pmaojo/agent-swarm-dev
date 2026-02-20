#!/bin/bash
# Start all services for agent-swarm-dev
# 1. FastEmbed server (port 11434)
# 2. Synapse (port 50051)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📦 Starting Agent Swarm Dev Services..."

# Check for FastEmbed
if ! curl -s http://localhost:11434/ >/dev/null 2>&1; then
    echo "▶️  Starting FastEmbed server..."
    cd "$PROJECT_DIR"
    python3 scripts/embeddings_server.py --port 11434 &
    sleep 3
else
    echo "✅ FastEmbed already running"
fi

# Check for Synapse
if ! curl -s http://localhost:50051 >/dev/null 2>&1; then
    echo "▶️  Starting Synapse..."
    cd "$PROJECT_DIR"
    EMBEDDING_PROVIDER=remote ./synapse &
    sleep 3
else
    echo "✅ Synapse already running"
fi

echo "🎉 All services ready!"
echo "   - FastEmbed: http://localhost:11434"
echo "   - Synapse: localhost:50051"
