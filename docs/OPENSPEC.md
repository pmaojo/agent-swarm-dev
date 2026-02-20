# OpenSpec Integration

Spec-driven development (SDD) framework for AI coding assistants.

## Install

```bash
npm install -g @fission-ai/openspec@latest
```

## Commands

| Command | Description |
|---------|-------------|
| `/opsx:new <feature>` | Create new feature proposal |
| `/opsx:ff` | Generate full planning docs (proposal, specs, design, tasks) |
| `/opsx:apply` | Implement tasks |
| `/opsx:archive` | Archive completed feature |
| `/opsx:onboard` | Initial setup |

## Usage with Swarm

1. Tell AI: `/opsx:new <feature>`
2. AI creates `openspec/changes/<feature>/`
3. Review proposal, specs, design
4. `/opsx:apply` to implement

## OpenClaw Integration

OpenSpec works with OpenClaw via the same slash commands. Add to your OpenClaw config:

```json
{
  "mcpServers": {
    "swarm": {
      "command": "python3",
      "args": ["scripts/swarm_mcp.py"]
    }
  }
}
```

Then use `/opsx:*` commands in your prompts.
