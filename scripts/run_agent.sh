#!/bin/bash
# Run a specific agent wrapper

AGENT_NAME="${1:-orchestrator}"
shift
TASK="$@"

if [ -z "$TASK" ]; then
  echo "Usage: $0 <agent-name> <task>"
  exit 1
fi

echo "🤖 Running agent: $AGENT_NAME"
echo "📋 Task: $TASK"

SCRIPT_DIR=$(dirname "$0")
AGENTS_DIR="$SCRIPT_DIR/../sdk/python/agents"

case $AGENT_NAME in
  orchestrator)
    python3 "$AGENTS_DIR/orchestrator.py" "$TASK"
    ;;
  coder)
    python3 "$AGENTS_DIR/coder.py" "$TASK"
    ;;
  reviewer)
    # Check if reviewer exists as standalone executable
    if [ -f "$AGENTS_DIR/reviewer.py" ]; then
        python3 "$AGENTS_DIR/reviewer.py" "$TASK"
    else
        echo "❌ Reviewer agent script not found or not standalone."
        exit 1
    fi
    ;;
  deployer)
    if [ -f "$AGENTS_DIR/deployer.py" ]; then
        python3 "$AGENTS_DIR/deployer.py" "$TASK"
    else
        echo "❌ Deployer agent script not found or not standalone."
        exit 1
    fi
    ;;
  *)
    echo "❌ Unknown agent: $AGENT_NAME"
    echo "Available agents: orchestrator, coder, reviewer, deployer"
    exit 1
    ;;
esac
