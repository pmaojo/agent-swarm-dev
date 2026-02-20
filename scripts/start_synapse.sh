#!/bin/bash
# Start Synapse with Remote Embeddings
# Requires FastEmbed server running on port 11434

set -e

SYNAPSE_BINARY="${SYNAPSE_BINARY:-./synapse}"
EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-remote}"
EMBEDDING_API_URL="${EMBEDDING_API_URL:-http://localhost:11434/api/embeddings}"

echo "🚀 Starting Synapse (Light Mode)"
echo "   Embedding Provider: $EMBEDDING_PROVIDER"
echo "   Embedding URL: $EMBEDDING_API_URL"

export EMBEDDING_PROVIDER
export EMBEDDING_API_URL

$SYNAPSE_BINARY "$@"
