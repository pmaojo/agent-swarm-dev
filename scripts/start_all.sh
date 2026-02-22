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
if [ -f "$PROJECT_DIR/.env" ]; then
    echo "📄 Loading environment from $PROJECT_DIR/.env..."
    set -a
    source "$PROJECT_DIR/.env"
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
SYNAPSE_PORT=${SYNAPSE_GRPC_PORT:-50051}
if ! nc -z localhost $SYNAPSE_PORT 2>/dev/null; then
    echo "▶️  Starting Synapse (Port: $SYNAPSE_PORT)..."
    # Use local synapse-data (respect env var)
    export GRAPH_STORAGE_PATH="${GRAPH_STORAGE_PATH:-./synapse-data}"
    export EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-remote}"

    # Run synapse in background
    ./synapse > synapse.log 2>&1 &
    sleep 3
else
    echo "✅ Synapse already running on $SYNAPSE_PORT"
fi

# 4. Start Unified Swarmd Orchestrator
if ! pgrep -f "swarmd" > /dev/null; then
    echo "▶️  Starting Swarm Orchestrator (swarmd)..."
    # Ensure swarmd is built
    if [ ! -f "$PROJECT_DIR/target/release/swarmd" ]; then
        echo "🔨 Building swarmd..."
        cargo build --release -p swarmd > /dev/null 2>&1
    fi
    nohup ./target/release/swarmd > swarmd.log 2>&1 &
    sleep 2
else
    echo "✅ Swarm Orchestrator already running"
fi

echo "🎉 All services ready!"
echo "   - FastEmbed: http://localhost:11434"
echo "   - Synapse: localhost:$SYNAPSE_PORT (Data: ./synapse-data)"
echo "   - Swarmd (Gateway/Web/Bots): Active (Logs: swarmd.log)"
