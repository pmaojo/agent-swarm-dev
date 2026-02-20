#!/bin/bash
# Setup Synapse for Agent Swarm Dev

echo "📦 Setting up Synapse..."

# Create data directory
mkdir -p /root/.openclaw/workspace/synapse-data

# Check if binary exists
if [ ! -f "/root/.openclaw/workspace/synapse" ]; then
    echo "⬇️  Downloading Synapse binary..."
    curl -L -o /root/.openclaw/workspace/synapse \
        "https://github.com/pmaojo/synapse-engine/releases/download/v0.8.4/synapse-linux-x64"
    chmod +x /root/.openclaw/workspace/synapse
fi

# Check GLIBC version
echo "🔍 Checking GLIBC version..."
ldd --version | head -1

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run Synapse:"
echo "  ./scripts/start_synapse.sh"
echo ""
echo "Or directly:"
echo "  GRAPH_STORAGE_PATH=/root/.openclaw/workspace/synapse-data /root/.openclaw/workspace/synapse --mcp"
