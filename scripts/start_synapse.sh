#!/bin/bash
# Start Synapse (RDF-only — memory is 100% explicit triples, no embeddings)

set -e

SYNAPSE_BINARY="${SYNAPSE_BINARY:-./synapse}"
GRAPH_STORAGE_PATH="${GRAPH_STORAGE_PATH:-data/graphs}"

echo "🚀 Starting Synapse"
echo "   Storage Path: $GRAPH_STORAGE_PATH"

export GRAPH_STORAGE_PATH

$SYNAPSE_BINARY "$@"
