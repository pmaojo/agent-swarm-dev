# Agent Instructions

## Startup

At the beginning of EVERY task, you MUST run the following command to ensure the environment is up-to-date and services are running:

```bash
source scripts/start_all.sh
```

This script will:
1. Compile the latest version of Synapse (light mode).
2. Start the FastEmbed server.
3. Start the Synapse server.

Do not proceed until you see "🎉 All services ready!".
