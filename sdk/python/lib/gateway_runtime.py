import asyncio
import json
import uuid
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Literal, Tuple
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, Request, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
# Add path to root
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)

from agents.orchestrator import OrchestratorAgent

# Godot Integration
from lib.godot_bridge.fog import FogService
from lib.character_profiles import CharacterRegistry, JsonCharacterProfileSource
from lib.contracts import (
    ActiveQuest,
    CharacterLoadoutSelection,
    ControlCommand,
    ControlCommandAck,
    EventAck,
    EventType,
    CountryState,
    GameState,
    GatewayEvent,
    GraphData,
    GraphEdge,
    GraphNode,
    PartyMember,
    QuestStatus,
    RepositoryState,
    ServiceHealth,
    ServiceState,
    SystemStatus,
)
from lib.knowledge_tree import discover_catalog_assets, fetch_knowledge_tree, ingest_custom_knowledge_node
from lib.combat_events import CombatEventFactory, ServiceMetrics, evaluate_service_health
from lib.godot_bridge.templates import (
    AGENT_UNIT_GD,
    FOG_MANAGER_GD,
    BRIDGE_GD,
    CITADEL_MANAGER_GD,
    BUILDING_GD
)

# --- Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()
combat_event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=256)
_service_metric_history: Dict[str, ServiceMetrics] = {}

# --- Stats Helper ---
# Global Orchestrator instance
orch = OrchestratorAgent()
fog_service = FogService(orch)

PROFILE_SOURCE_PATH = Path(__file__).resolve().parents[1] / "data" / "character_profiles.json"
character_registry = CharacterRegistry(JsonCharacterProfileSource(PROFILE_SOURCE_PATH))

def fetch_stats() -> Dict[str, Any]:
    """Fetch real-time stats from Synapse."""
    try:
        # 1. Operational Status
        status = orch.check_operational_status()

        # 2. Pending Tasks
        pending_query = 'SELECT (COUNT(?s) as ?count) WHERE { ?s <http://swarm.os/session_status> "pending" }'
        pending_res = orch.query_graph(pending_query, namespace="default")
        pending = 0
        if pending_res:
            val = pending_res[0].get('?count') or pending_res[0].get('count')
            if val: pending = int(val)

        # 3. Failed Tasks (All time? Or today? Let's do all time for now as failure log persists)
        failed_query = 'PREFIX nist: <http://nist.gov/caisi/> SELECT (COUNT(?s) as ?count) WHERE { ?s nist:resultState "on_failure" }'
        failed_res = orch.query_graph(failed_query, namespace="default")
        failed = 0
        if failed_res:
            val = failed_res[0].get('?count') or failed_res[0].get('count')
            if val: failed = int(val)

        # 4. Daily Spend
        today = datetime.now().strftime("%Y-%m-%d")
        spend_query = f"""
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT (SUM(?amount) as ?total)
        WHERE {{
            ?event a swarm:SpendEvent .
            ?event swarm:date "{today}" .
            ?event swarm:amount ?amount .
        }}
        """
        spend_res = orch.query_graph(spend_query, namespace="default")
        spend = 0.0
        if spend_res:
            val = spend_res[0].get('?total') or spend_res[0].get('total')
            if val: spend = float(val)

        # 5. Active Agents (List of agents from schema)
        active_agents = list(orch.agents.keys())

        # 6. Budget Utilization
        max_budget = 10.0 # Default fallback
        try:
            budget_res = orch.query_graph('PREFIX swarm: <http://swarm.os/ontology/> SELECT ?max WHERE { <http://swarm.os/ontology/Finance> swarm:maxBudget ?max } LIMIT 1', namespace="default")
            if budget_res:
                 val = budget_res[0].get('?max') or budget_res[0].get('max')
                 if val: max_budget = float(val)
        except:
            pass

        utilization = (spend / max_budget * 100) if max_budget > 0 else 0.0

        return {
            "status": status,
            "pending_tasks": pending,
            "failed_tasks": failed,
            "daily_spend": spend,
            "budget_utilization": f"{utilization:.1f}%",
            "active_agents": active_agents,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {"error": str(e)}

def _emit_combat_event(event: GatewayEvent) -> None:
    payload = {"type": event.type.value, "payload": event.model_dump()}
    if combat_event_queue.full():
        try:
            combat_event_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        combat_event_queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass


def _service_metrics_from_health(health: ServiceHealth) -> Tuple[float, float]:
    mapping: Dict[ServiceHealth, Tuple[float, float]] = {
        ServiceHealth.HEALTHY: (60.0, 0.01),
        ServiceHealth.DEGRADED: (320.0, 0.10),
        ServiceHealth.UNDER_ATTACK: (930.0, 0.25),
        ServiceHealth.HALTED: (1500.0, 1.0),
    }
    return mapping.get(health, (80.0, 0.02))


def _build_service_state(country_id: str, service_id: str, service_name: str, system_status_raw: str, budget_ratio: float) -> ServiceState:
    system_status = SystemStatus(system_status_raw) if system_status_raw in {s.value for s in SystemStatus} else SystemStatus.UNKNOWN
    baseline_latency, baseline_error = _service_metrics_from_health(ServiceHealth.HEALTHY)

    test_failures = 0
    worker_errors = 0
    try:
        fail_res = orch.query_graph(
            f'PREFIX nist: <http://nist.gov/caisi/> SELECT (COUNT(?s) as ?count) WHERE {{ ?s nist:resultState "on_failure" }}',
            namespace="default",
        )
        if fail_res:
            val = fail_res[0].get('?count') or fail_res[0].get('count')
            test_failures = int(val or 0)
    except Exception:
        test_failures = 0

    try:
        worker_res = orch.query_graph(
            'PREFIX swarm: <http://swarm.os/ontology/> SELECT (COUNT(?event) as ?count) WHERE { ?event a swarm:WorkerErrorEvent . }',
            namespace="default",
        )
        if worker_res:
            val = worker_res[0].get('?count') or worker_res[0].get('count')
            worker_errors = int(val or 0)
    except Exception:
        worker_errors = 0

    latency_ms = baseline_latency + (test_failures * 22.0) + (worker_errors * 40.0)
    error_rate = min(1.0, baseline_error + (test_failures * 0.012) + (worker_errors * 0.02) + max(0.0, budget_ratio - 0.8) * 0.5)

    metrics = evaluate_service_health(latency_ms=latency_ms, error_rate=error_rate, system_status=system_status)
    service_key = f"{country_id}:{service_id}"
    previous = _service_metric_history.get(service_key)

    spawned = CombatEventFactory.from_test_failures(service_id=service_id, service_name=service_name, failures=test_failures)
    if spawned is not None and test_failures > 0:
        _emit_combat_event(spawned)

    damaged = CombatEventFactory.from_worker_errors(service_id=service_id, service_name=service_name, errors=worker_errors)
    if damaged is not None:
        _emit_combat_event(damaged)

    for budget_event in CombatEventFactory.from_budget_utilization(
        service_id=service_id,
        service_name=service_name,
        budget_utilization_percent=budget_ratio * 100.0,
    ):
        _emit_combat_event(budget_event)

    if previous is not None:
        for recovered_event in CombatEventFactory.from_service_transition(
            service_id=service_id,
            service_name=service_name,
            previous=previous,
            current=metrics,
            system_status=system_status,
        ):
            _emit_combat_event(recovered_event)

    _service_metric_history[service_key] = metrics

    return ServiceState(
        id=service_id,
        name=service_name,
        health=metrics.health,
        hp=metrics.hp,
        latency_ms=round(metrics.latency_ms, 2),
        error_rate=round(metrics.error_rate, 4),
    )


def fetch_game_state() -> Dict[str, Any]:
    """Fetch RPG Game State."""
    try:
        # 1. System Status
        status = orch.check_operational_status()

        # 2. Daily Budget
        today = datetime.now().strftime("%Y-%m-%d")
        spend_query = f"""
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT (SUM(?amount) as ?total)
        WHERE {{
            ?event a swarm:SpendEvent .
            ?event swarm:date "{today}" .
            ?event swarm:amount ?amount .
        }}
        """
        spend_res = orch.query_graph(spend_query, namespace="default")
        spend = 0.0
        if spend_res:
            val = spend_res[0].get('?total') or spend_res[0].get('total')
            if val: spend = float(val)

        max_budget = 10.0
        try:
            budget_res = orch.query_graph('PREFIX swarm: <http://swarm.os/ontology/> SELECT ?max WHERE { <http://swarm.os/ontology/Finance> swarm:maxBudget ?max } LIMIT 1', namespace="default")
            if budget_res:
                 val = budget_res[0].get('?max') or budget_res[0].get('max')
                 if val: max_budget = float(val)
        except:
            pass

        daily_budget = {
            "max": max_budget,
            "spent": spend,
            "unit": "USD"
        }

        # 3. Party (Character Profiles)
        party = []
        for profile in character_registry.list_profiles():
            hp = profile.loadout.hit_points
            try:
                fail_q = (
                    'PREFIX nist: <http://nist.gov/caisi/> '
                    'PREFIX prov: <http://www.w3.org/ns/prov#> '
                    f'SELECT (COUNT(?exec) as ?count) WHERE {{ ?exec prov:wasAssociatedWith <http://swarm.os/agent/{profile.display_name}> ; nist:resultState "on_failure" }}'
                )
                fail_res = orch.query_graph(fail_q)
                if fail_res:
                    val = fail_res[0].get('?count') or fail_res[0].get('count')
                    if val:
                        fails = int(val)
                        hp = max(0, profile.loadout.hit_points - (fails * 5))
            except Exception:
                pass

            party.append(
                PartyMember(
                    id=profile.agent_id,
                    name=profile.display_name,
                    **{"class": profile.class_name},
                    level=profile.level,
                    stats={
                        "hp": hp,
                        "mana": profile.loadout.mana,
                        "success_rate": profile.base_success_rate,
                    },
                    current_action=profile.current_action,
                    location=profile.location,
                )
            )

        # 4. Active Quests (Trello)
        active_quests = []
        status_map = {
            "REQUIREMENTS": QuestStatus.REQUIREMENTS,
            "DESIGN": QuestStatus.DESIGN,
            "TODO": QuestStatus.READY,
            "IN PROGRESS": QuestStatus.IN_PROGRESS,
        }
        try:
            for card in orch.bridge.get_cards_in_list("REQUIREMENTS"):
                active_quests.append(ActiveQuest(id=card['id'], title=card['name'], status=status_map["REQUIREMENTS"]))
            for card in orch.bridge.get_cards_in_list("DESIGN"):
                active_quests.append(ActiveQuest(id=card['id'], title=card['name'], status=status_map["DESIGN"]))
            for card in orch.bridge.get_cards_in_list("TODO"):
                 active_quests.append(ActiveQuest(id=card['id'], title=card['name'], status=status_map["TODO"]))
            for card in orch.bridge.get_cards_in_list("IN PROGRESS"):
                 active_quests.append(ActiveQuest(id=card['id'], title=card['name'], status=status_map["IN PROGRESS"]))
        except Exception: pass

        # 5. Fog of War
        fog_map = fog_service.get_fog_state()

        # 6. Repositories (Citadel Buildings)
        # Identify repos by querying for files and extracting roots, or checking explicit config.
        # For now, default to the current root "." and identify by folder name.
        repositories = []
        try:
            repositories.append(RepositoryState(id="repo-root", name="Main Citadel", swarm=[]))
        except Exception: pass

        normalized_status = status if status in {s.value for s in SystemStatus} else SystemStatus.UNKNOWN.value
        budget_ratio = (spend / max_budget) if max_budget > 0 else 0.0

        countries = [
            CountryState(
                id="country-core",
                name="The Core Empire",
                services=[
                    _build_service_state("country-core", "service-orchestrator", "orchestrator", normalized_status, budget_ratio),
                    _build_service_state("country-core", "service-gateway", "gateway", normalized_status, budget_ratio),
                ],
            ),
            CountryState(
                id="country-frontend",
                name="The Front-End Republic",
                services=[
                    _build_service_state("country-frontend", "service-visualizer", "visualizer", normalized_status, budget_ratio),
                    _build_service_state("country-frontend", "service-web", "web", normalized_status, budget_ratio),
                ],
            ),
            CountryState(
                id="country-security",
                name="The Security Kingdom",
                services=[
                    _build_service_state("country-security", "service-guardian", "guardian", normalized_status, budget_ratio),
                ],
            ),
        ]

        catalog_assets = discover_catalog_assets(Path(__file__).resolve().parents[3])
        knowledge_tree = fetch_knowledge_tree(
            query_graph=lambda query: orch.query_graph(query, namespace="default"),
            ingest_triples=lambda triples: orch.ingest_triples(triples, namespace="default"),
            catalog_assets=catalog_assets,
        )

        game_state = GameState(
            system_status=normalized_status,
            selected_character_id=character_registry.selected_character_id(),
            selected_character_loadout=character_registry.selected_character_loadout(),
            daily_budget=daily_budget,
            party=party,
            active_quests=active_quests,
            fog_map=fog_map,
            repositories=repositories,
            countries=countries,
            knowledge_tree=knowledge_tree,
        )

        return game_state.model_dump(by_alias=True)

    except Exception as e:
        print(f"Error fetching game state: {e}")
        return {"error": str(e)}

def fetch_graph_nodes() -> Dict[str, Any]:
    """Fetch Cytoscape Graph Nodes (Last 20 Triples)."""
    try:
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o . } LIMIT 20"
        results = orch.query_graph(query)

        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        node_ids = set()

        def add_node(uri_or_literal, node_type="unknown"):
            n_id = str(uri_or_literal).strip('<>"')
            label = n_id.split('/')[-1] if '/' in n_id else n_id
            if n_id not in node_ids:
                nodes.append(GraphNode(id=n_id, label=label, type=node_type))
                node_ids.add(n_id)
            return n_id

        for row in results:
            s = row.get("?s") or row.get("s")
            p = row.get("?p") or row.get("p")
            o = row.get("?o") or row.get("o")
            if s and p and o:
                s_id = add_node(s, "subject")
                o_id = add_node(o, "object")
                p_label = str(p).strip('<>').split('/')[-1].split('#')[-1]
                edges.append(GraphEdge(source=s_id, target=o_id, label=p_label))

        return GraphData(nodes=nodes, edges=edges).model_dump(by_alias=True)
    except Exception as e:
        print(f"Error fetching graph nodes: {e}")
        return GraphData().model_dump(by_alias=True)

def fetch_codegraph() -> Dict[str, Any]:
    """Fetch CodeGraph for visualization."""
    try:
        query = """
        PREFIX swarm: <http://swarm.os/ontology/>
        PREFIX codegraph: <http://swarm.os/ontology/codegraph/>

        SELECT ?s ?type ?p ?o WHERE {
            ?s a ?type .
            FILTER(?type IN (codegraph:File, codegraph:Class, codegraph:Function))
            OPTIONAL {
                ?s ?p ?o .
                FILTER(?p IN (swarm:calls, swarm:references, swarm:inheritsFrom, swarm:hasSymbol))
            }
        }
        """
        results = orch.query_graph(query)

        nodes = {}
        edges = []

        for row in results:
            s_uri = row.get("?s") or row.get("s")
            sType = row.get("?type") or row.get("type")

            # Add Node
            if s_uri and s_uri not in nodes:
                label = s_uri.split('/')[-1]
                if '#' in label: label = label.split('#')[-1]
                nodes[s_uri] = {"id": s_uri, "type": str(sType).split('/')[-1], "label": label}

            # Add Edge
            p = row.get("?p") or row.get("p")
            o = row.get("?o") or row.get("o")
            if p and o:
                p_label = str(p).split('/')[-1].split('#')[-1]
                edges.append({"from": s_uri, "to": str(o), "type": p_label})

        return {"nodes": list(nodes.values()), "edges": edges}
    except Exception as e:
        print(f"Error fetching CodeGraph: {e}")
        return {"nodes": [], "edges": []}

async def broadcast_stats_loop():
    """Background task to push stats."""
    while True:
        try:
            stats = await asyncio.to_thread(fetch_game_state) # Use enriched game state
            if stats:
                await manager.broadcast({"type": "game_state_update", "payload": stats})
        except Exception as e:
            print(f"Broadcast error: {e}")
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(broadcast_stats_loop())
    yield
    # Shutdown
    task.cancel()
    orch.close()

app = FastAPI(lifespan=lifespan)

# Add Middleware for Security Headers (COOP/COEP for Godot Web)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status")
async def get_status(): return await asyncio.to_thread(fetch_stats)

@app.get("/api/v1/game-state")
async def get_game_state(): return await asyncio.to_thread(fetch_game_state)

@app.get("/api/v1/graph-nodes")
async def get_graph_nodes(): return await asyncio.to_thread(fetch_graph_nodes)


class CharacterSelectionRequest(BaseModel):
    character_id: str


class CharacterSelectionResponse(BaseModel):
    selected_character_id: str


class CharacterLoadoutSaveRequest(BaseModel):
    character_id: str
    loadout: CharacterLoadoutSelection


class CharacterLoadoutSaveResponse(BaseModel):
    selected_character_id: str
    selected_character_loadout: CharacterLoadoutSelection


class KnowledgeNodeDocumentationResponse(BaseModel):
    node_id: str
    documentation: str


@app.get("/api/v1/characters")
async def get_characters() -> Dict[str, Any]:
    selected_character_id = character_registry.selected_character_id()
    return {
        "selected_character_id": selected_character_id,
        "characters": [profile.model_dump() for profile in character_registry.list_profiles()],
    }


@app.post("/api/v1/characters/select")
async def select_character(payload: CharacterSelectionRequest) -> Dict[str, Any]:
    try:
        selected_profile = character_registry.select_character(payload.character_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown character_id: {payload.character_id}") from exc

    return CharacterSelectionResponse(selected_character_id=selected_profile.id).model_dump()


@app.post("/api/v1/characters/loadout")
async def save_character_loadout(payload: CharacterLoadoutSaveRequest) -> Dict[str, Any]:
    try:
        selected_profile = character_registry.configure_selected_loadout(payload.character_id, payload.loadout)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown character_id: {payload.character_id}") from exc

    return CharacterLoadoutSaveResponse(
        selected_character_id=selected_profile.id,
        selected_character_loadout=payload.loadout,
    ).model_dump()


@app.get("/api/v1/knowledge-tree/nodes/{node_id}/documentation")
async def get_knowledge_node_documentation(node_id: str) -> Dict[str, Any]:
    knowledge_tree = fetch_knowledge_tree(
        query_graph=lambda query: orch.query_graph(query, namespace="default"),
        ingest_triples=lambda triples: orch.ingest_triples(triples, namespace="default"),
        catalog_assets=discover_catalog_assets(Path(__file__).resolve().parents[3]),
    )
    for node in knowledge_tree:
        if node.id == node_id:
            return KnowledgeNodeDocumentationResponse(
                node_id=node.id,
                documentation=node.documentation,
            ).model_dump()
    raise HTTPException(status_code=404, detail=f"Unknown knowledge node id: {node_id}")


def _validate_control_command(payload: Dict[str, Any]) -> ControlCommand:
    try:
        return ControlCommand.model_validate(payload)
    except ValidationError as exc:
        errors = exc.errors()
        loadout_errors = [err for err in errors if str(err.get("loc", "")).startswith("('loadout'")]
        if loadout_errors:
            raise HTTPException(status_code=422, detail=f"Invalid loadout payload: {loadout_errors}") from exc
        raise HTTPException(status_code=422, detail=f"Invalid control command payload: {errors}") from exc


@app.post("/api/v1/control/commands")
async def post_control_command(command_payload: Dict[str, Any]):
    command = _validate_control_command(command_payload)
    await manager.broadcast({"type": "CONTROL_COMMAND", "payload": command.model_dump()})
    return ControlCommandAck(command=command).model_dump()


@app.post("/api/v1/events")
async def post_event(event: GatewayEvent):
    await manager.broadcast({"type": event.type, "payload": event.model_dump()})
    return EventAck(event=event).model_dump()


@app.websocket("/api/v1/events/combat/stream")
async def combat_event_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            try:
                event_payload = await asyncio.wait_for(combat_event_queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "keepalive"})
                continue
            await websocket.send_json(event_payload)
    except WebSocketDisconnect:
        return

# --- Godot Script Endpoints ---
@app.get("/api/v1/godot/scripts/agent")
async def get_agent_script(): return {"script": AGENT_UNIT_GD}

@app.get("/api/v1/godot/scripts/fog")
async def get_fog_script(): return {"script": FOG_MANAGER_GD}

@app.get("/api/v1/godot/scripts/bridge")
async def get_bridge_script(): return {"script": BRIDGE_GD}

@app.get("/api/v1/godot/scripts/citadel")
async def get_citadel_script(): return {"script": CITADEL_MANAGER_GD}

@app.get("/api/v1/godot/scripts/building")
async def get_building_script(): return {"script": BUILDING_GD}



class KnowledgeNodeIngestRequest(BaseModel):
    node_id: str
    domain: str
    name: str
    capability: str
    level: int = 1
    budget_cost: float = 1.0
    time_cost_hours: int = 1
    prerequisites: List[str] = Field(default_factory=list)
    docs_text: str = ""
    source_type: str = "custom"
    source_ref: str = "game://manual"


@app.post("/api/v1/knowledge-tree/nodes")
async def ingest_knowledge_tree_node(payload: KnowledgeNodeIngestRequest):
    node = ingest_custom_knowledge_node(
        ingest_triples=lambda triples: orch.ingest_triples(triples, namespace="default"),
        node_id=payload.node_id,
        domain=payload.domain,
        name=payload.name,
        capability=payload.capability,
        level=payload.level,
        budget_cost=payload.budget_cost,
        time_cost_hours=payload.time_cost_hours,
        prerequisites=payload.prerequisites,
        docs_text=payload.docs_text,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
    )
    return {"status": "ingested", "node": node.model_dump()}

class MissionAssignment(BaseModel):
    agent_id: str
    repo_id: str
    task: str

@app.post("/api/v1/mission/assign")
async def assign_mission(mission: MissionAssignment):
    """
    Assigns a mission to an agent for a specific repository.
    Broadcasts the event to Godot.
    """
    try:
        command = ControlCommand(command="ASSIGN_MISSION", agent_id=mission.agent_id, repo_id=mission.repo_id, task=mission.task)
        payload = {"type": EventType.MISSION_ASSIGNED, "payload": command.model_dump()}
        await manager.broadcast(payload)
        return ControlCommandAck(command=command).model_dump()
    except Exception as e:
        print(f"Error assigning mission: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/api/v1/codegraph/stream")
async def codegraph_stream(websocket: WebSocket):
    """Streams the CodeGraph to Godot."""
    await websocket.accept()
    try:
        while True:
            graph_data = await asyncio.to_thread(fetch_codegraph)
            await websocket.send_json(graph_data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("CodeGraph Client disconnected")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        try: initial_data = await websocket.receive_json()
        except:
            await manager.disconnect(websocket)
            return

        if initial_data.get("method") == "connect":
            await websocket.send_json({
                "type": "hello-ok",
                "health": "ok",
                "version": "1.2.0-godot-conquest",
                "agents": list(orch.agents.keys())
            })

        while True:
            data = await websocket.receive_json()
            method = data.get("method")
            if method == "agent.run":
                req_id = data.get("id")
                params = data.get("params", {})
                task = params.get("task")
                session_id = params.get("session", "default")
                if not task:
                    await websocket.send_json({"status": "error", "id": req_id, "error": "No task provided"})
                    continue
                await websocket.send_json({"status": "accepted", "id": req_id})
                try:
                    result = await asyncio.to_thread(orch.run, task, session_id=session_id)
                    await websocket.send_json({"status": "ok", "id": req_id, "payload": result})
                except Exception as e:
                    await websocket.send_json({"status": "error", "id": req_id, "error": str(e)})
            elif method == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect: manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

class HardeningEvent(BaseModel):
    type: str # "ALERT", "STATIC_ANALYSIS", "CONTRACT_FAILURE"
    message: str
    details: Dict[str, Any] = {}
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "INFO"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

@app.post("/api/v1/events/hardening")
async def receive_hardening_event(event: HardeningEvent):
    """
    Receives hardening events from agents/LLM and broadcasts them to Godot.
    """
    try:
        gateway_event = GatewayEvent(
            type=EventType.HARDENING_EVENT,
            message=event.message,
            details=event.details,
            severity=event.severity,
            timestamp=event.timestamp,
        )
        payload = {"type": gateway_event.type, "payload": gateway_event.model_dump()}
        await manager.broadcast(payload)
        return EventAck(event=gateway_event).model_dump()
    except Exception as e:
        print(f"Error broadcasting hardening event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/{channel}")
async def inbound_webhook(channel: str, request: Request):
    try: data = await request.json()
    except: raise HTTPException(status_code=400, detail="Invalid JSON")
    session_id = data.get("session_id") or data.get("sender_id") or str(uuid.uuid4())
    text = data.get("text") or data.get("message", {}).get("text")
    if not text: raise HTTPException(status_code=400, detail="No text found in message")
    msg_id = f"http://swarm.os/msg/{uuid.uuid4()}"
    session_uri = f"http://swarm.os/session/{session_id}"
    triples = [
        {"subject": msg_id, "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": "http://synapse.os/memory#UserInstruction"},
        {"subject": msg_id, "predicate": "http://synapse.os/memory#content", "object": f'"{text}"'},
        {"subject": session_uri, "predicate": "http://swarm.os/has_pending_task", "object": msg_id},
        {"subject": session_uri, "predicate": "http://swarm.os/session_status", "object": '"pending"'}
    ]
    try:
        orch.ingest_triples(triples, namespace="default")
        return {"status": "accepted", "msg_id": msg_id, "session_id": session_id}
    except Exception as e:
        print(f"Webhook ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Static Files & SPA Fallback ---
# Mount commander-dashboard/dist if it exists
STATIC_DIR = Path(__file__).parent.parent / "commander-dashboard" / "dist"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        # Check if the request is an API request; if not, serve index.html
        if request.url.path.startswith("/api"):
             raise HTTPException(status_code=404, detail="API route not found")
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
             return FileResponse(index_path)
        return HTTPException(status_code=404, detail="Not Found")
else:
    print(f"Warning: Static directory {STATIC_DIR} not found. Frontend will not be served.")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 18789))
    uvicorn.run(app, host="0.0.0.0", port=port)
