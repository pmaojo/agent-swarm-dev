

# Cyberpunk RPG Command Center Dashboard

## Overview
A dark, neon-accented dashboard that presents an AI Agent Swarm as an RPG party. The UI connects to a FastAPI backend via polling and renders agents, quests, a knowledge graph, and sovereign controls — all with a high-tech cyberpunk aesthetic.

---

## Design System
- **Dark base** with neon accent colors: cyan (agents), matrix-green (success), amber (warnings), crimson (danger)
- Custom CSS variables for the cyberpunk palette applied globally
- Glowing borders, pulsing animations, and subtle scan-line effects for the "magical" feel
- Lucide icons throughout, mapped to character classes (Music for Bard, Wand2 for Wizard, Sword for Warrior, Shield for Paladin)

---

## Layout Structure
- **Left Sidebar** — The RPG Party (agent character cards)
- **Top Header** — System status indicator + daily budget bar
- **Main Area** — Tabbed view switching between Knowledge Graph and Quest Log
- **Footer Bar** — Sovereign Controls (Kill Switch + Guardrail Log)

---

## Feature 1: RPG Party Sidebar
- Fetch agent data from `GET /api/v1/game-state` (mocked initially)
- Each agent rendered as a **Character Card** showing:
  - Name, class icon, and class title
  - **Mana Bar** (daily token budget) — cyan glowing progress bar
  - **Health Bar** (success rate) — green-to-red gradient progress bar
  - Current action as a scrolling "Battle Log" snippet
  - Location badge
- Cards glow/pulse when agent is actively working

## Feature 2: The Living Knowledge Graph
- Integrate **Cytoscape.js** to render interactive node-edge graph
- Data fetched from `GET /api/v1/graph-nodes` (mocked initially)
- Cyberpunk-styled nodes with neon outlines
- **Click interaction**: selecting a node opens a detail side panel showing semantic triples and metadata
- **Pulse animation** on nodes linked to an actively-executing agent tool
- Zoom, pan, and fit controls

## Feature 3: The Quest Log
- Kanban-style board with four columns: Requirements, Design, Todo, In Progress
- Cards sourced from `active_quests` in the game state
- Each card shows quest title, difficulty badge (color-coded), and assigned agent
- Cyberpunk card styling with neon border accents

## Feature 4: Sovereign Controls (Footer)
- **EMERGENCY SEAL button**: prominent crimson kill switch that sends `POST /api/v1/halt`
- When system status is `HALTED`, a full-screen red **"System Interdicted"** overlay appears with pulsing warning animation, blocking all other interaction
- **Guardrail Log**: real-time scrolling feed of NIST security interceptions (mocked initially)

## Feature 5: Data Polling & Mock Layer
- All API calls abstracted into a service layer with React Query
- **5-second polling interval** on game state and graph data
- Mock data baked in as fallback so the dashboard renders fully without a live backend
- Status indicators show connection health (connected/polling/disconnected)

---

## Pages
1. **Dashboard (/)** — The full command center with all views integrated
