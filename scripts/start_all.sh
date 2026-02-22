#!/bin/bash
# Start all services for agent-swarm-dev
# 1. Ensure Synapse is built (Light Version)
# 2. FastEmbed server (port 11434)
# 3. Synapse (port 50051)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📦 Starting Agent Swarm Dev Services..."

# Load .env if present
if [ -f ".env" ]; then
    echo "📄 Loading environment from .env..."
    set -a
    source .env
    set +a
fi

# 1. Build Synapse
echo "🔨 Ensuring Synapse is built..."
cd "$PROJECT_DIR"
# Run setup_synapse.sh to build/update
if ! bash scripts/setup_synapse.sh; then
    echo "❌ Build failed!"
    exit 1
fi

# 2. Check for FastEmbed
if ! curl -s http://localhost:11434/ >/dev/null 2>&1; then
    echo "▶️  Starting FastEmbed server..."
    python3 scripts/embeddings_server.py --port 11434 > /dev/null 2>&1 &
    sleep 3
else
    echo "✅ FastEmbed already running"
fi

# 3. Check for Synapse
if ! curl -s http://localhost:50051 >/dev/null 2>&1; then
    echo "▶️  Starting Synapse..."
    # Use local synapse-data (respect env var)
    export GRAPH_STORAGE_PATH="${GRAPH_STORAGE_PATH:-./synapse-data}"
    export EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-remote}"

    # Run synapse in background
    ./synapse > synapse.log 2>&1 &
    sleep 3
else
    echo "✅ Synapse already running"
fi

echo "🎉 All services ready!"
echo "   - FastEmbed: http://localhost:11434"
echo "   - Synapse: localhost:50051 (Data: ./synapse-data)"
