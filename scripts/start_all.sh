#!/bin/bash
# Start all services for agent-swarm-dev
# 1. Ensure Synapse is built (Light Version)
# 2. FastEmbed server (port 11434)
# 3. Synapse (port 50051)
# 4. Swarmd Gateway (port 18789)
# 5. Swarm CLI (TUI)

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

# 4. Start Swarmd Gateway
if ! pgrep -f "swarmd$" > /dev/null; then
    echo "▶️  Starting Swarm Gateway (swarmd)..."
    # Build in debug mode
    cargo build -p swarmd > /dev/null 2>&1
    nohup ./target/debug/swarmd > swarmd.log 2>&1 &
    sleep 2
else
    echo "✅ Swarm Gateway already running"
fi

# 5. Start Trello Bridge
if ! pgrep -f "run_trello_bridge.py" > /dev/null; then
    echo "▶️  Starting Trello Bridge (Brain)..."
    nohup python3 scripts/run_trello_bridge.py > trello_bridge.log 2>&1 &
    sleep 2
else
    echo "✅ Trello Bridge already running"
fi

# 6. Start Swarm CLI (TUI)
if ! pgrep -f "swarm-cli" > /dev/null; then
    echo "▶️  Starting Swarm CLI (TUI)..."
    # Build CLI if needed
    cargo build -p swarmd --bin swarm-cli > /dev/null 2>&1
    # Start CLI in background (requires terminal)
    nohup ./target/debug/swarm-cli > swarm-cli.log 2>&1 &
    sleep 2
else
    echo "✅ Swarm CLI already running"
fi

echo "🎉 All services ready!"
echo "   - FastEmbed: http://localhost:11434"
echo "   - Synapse: localhost:$SYNAPSE_PORT (Data: ./synapse-data)"
echo "   - Swarm Gateway: http://localhost:18789"
echo "   - Trello Bridge: Active (Logs: trello_bridge.log)"
echo "   - Swarm CLI: Active (Neural Stream: swarm-cli.log)"
echo ""
echo "👉 You can now go to Trello and create a card in 'INBOX'!"
echo "👉 To see the agents thinking, run: tail -f swarm-cli.log"
