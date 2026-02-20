#!/bin/bash
# Start Synapse MCP Server

SYNAPSE_BIN="/root/.openclaw/workspace/synapse"
STORAGE_PATH="/root/.openclaw/workspace/synapse-data"

# Create storage directory
mkdir -p "$STORAGE_PATH"

# Run in MCP mode
exec "$SYNAPSE_BIN" --mcp
