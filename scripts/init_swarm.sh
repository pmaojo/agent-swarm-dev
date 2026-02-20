#!/bin/bash
# Agent Swarm Development System - Initialization Script

set -e

PROJECT_NAME="${1:-mi-proyecto}"
mkdir -p "$PROJECT_NAME"/{src,specs,agents,deploy}

# Create main SPEC.md
cat > "$PROJECT_NAME/SPEC.md" << 'EOF'
# Project Specification

## Overview
- **Name**: 
- **Type**: Agent Swarm Infrastructure
- **Goal**: 

## Agents

### orchestrator
- **INPUT**: User request
- **OUTPUT**: Task breakdown
- **DEPENDENCIES**: None

### coder
- **INPUT**: Task specification
- **OUTPUT**: Code implementation
- **DEPENDENCIES**: orchestrator

### reviewer
- **INPUT**: Code to review
- **OUTPUT**: Review feedback
- **DEPENDENCIES**: coder

### deployer
- **OUTPUT**: Deployed application
- **DEPENDENCIES**: reviewer

## Acceptance Criteria
- [ ] Agents can communicate via handoff
- [ ] Code compiles without errors
- [ ] Deploys to Vercel successfully
EOF

echo "✅ Project '$PROJECT_NAME' created!"
echo "📝 Edit SPEC.md to define your agents"
