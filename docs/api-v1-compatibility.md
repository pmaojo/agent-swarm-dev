# API v1 Compatibility (Godot + React)

This document defines the canonical `/api/v1` contract shared by the Python gateway and Rust gateway.

## Canonical resources

- `GET /api/v1/game-state` → `GameState`
- `GET /api/v1/graph-nodes` → `GraphData`
- `POST /api/v1/control/commands` → `ControlCommand` and returns `ControlCommandAck`
- `POST /api/v1/events` → `GatewayEvent` and returns `EventAck`

## Backward compatibility policy

1. **Minor additive only**: adding optional fields is allowed in v1.
2. **No semantic renaming**: existing fields (`system_status`, `active_quests`, `repositories`) must preserve meaning.
3. **Enums are stable**:
   - `system_status`: `OPERATIONAL | DEGRADED | OUTAGE | UNKNOWN`
   - `active_quests[].status`: `REQUIREMENTS | DESIGN | READY | IN_PROGRESS | DONE | BLOCKED`
4. **Breaking change process**:
   - create `/api/v2` in parallel,
   - keep `/api/v1` for at least one full release cycle,
   - provide migration notes for Godot and React consumers.

## Consumer notes

- Godot should treat unknown enum values as graceful fallback (`UNKNOWN`/`BLOCKED`).
- React should use schema-driven typing and reject malformed payloads at boundaries.
- Both clients must ignore unknown fields to support additive evolution.
