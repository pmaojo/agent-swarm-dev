import asyncio
import json
import uuid
import time
from typing import Dict, Any, List, Literal
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, Request, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agents.orchestrator import OrchestratorAgent

# Godot Integration
from lib.godot_bridge.fog import FogService
from lib.godot_bridge.templates import AGENT_UNIT_GD, FOG_MANAGER_GD

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

# --- Stats Helper ---
# Global Orchestrator instance
orch = OrchestratorAgent()
fog_service = FogService(orch)

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

        # 3. Party (Agents)
        party = []
        known_agents = ["ProductManager", "Architect", "Coder", "Reviewer", "Deployer"]

        rpg_classes = {
            "ProductManager": "Bard",
            "Architect": "Wizard",
            "Coder": "Warrior",
            "Reviewer": "Cleric",
            "Deployer": "Rogue"
        }

        locations = {
             "ProductManager": "The Requirements Hall",
             "Architect": "The Tower of Design",
             "Coder": "The Shell Dungeon",
             "Reviewer": "The Gate of Judgment",
             "Deployer": "The Cloud Kingdom"
        }

        for name in known_agents:
            stats = { "hp": 100, "mana": 80, "success_rate": "95%" }
            try:
                fail_q = f'PREFIX nist: <http://nist.gov/caisi/> PREFIX prov: <http://www.w3.org/ns/prov#> SELECT (COUNT(?exec) as ?count) WHERE {{ ?exec prov:wasAssociatedWith <http://swarm.os/agent/{name}> ; nist:resultState "on_failure" }}'
                fail_res = orch.query_graph(fail_q)
                if fail_res:
                    val = fail_res[0].get('?count') or fail_res[0].get('count')
                    if val:
                        fails = int(val)
                        stats["hp"] = max(0, 100 - (fails * 5))
            except: pass

            agent_data = {
                "id": f"agent-{name.lower()}",
                "name": name,
                "class": rpg_classes.get(name, "Villager"),
                "level": 5,
                "stats": stats,
                "current_action": "Idle",
                "location": locations.get(name, "Unknown")
            }
            party.append(agent_data)

        # 4. Active Quests (Trello)
        active_quests = []
        try:
            for card in orch.bridge.get_cards_in_list("REQUIREMENTS"):
                active_quests.append({"id": card['id'], "title": card['name'], "stage": "Requirements", "difficulty": "Medium", "rewards": ["XP"]})
            for card in orch.bridge.get_cards_in_list("DESIGN"):
                active_quests.append({"id": card['id'], "title": card['name'], "stage": "Design", "difficulty": "Hard", "rewards": ["Wisdom"]})
            for card in orch.bridge.get_cards_in_list("TODO"):
                 active_quests.append({"id": card['id'], "title": card['name'], "stage": "Ready", "difficulty": "Normal", "rewards": ["Gold"]})
            for card in orch.bridge.get_cards_in_list("IN PROGRESS"):
                 active_quests.append({"id": card['id'], "title": card['name'], "stage": "In Progress", "difficulty": "Hard", "rewards": ["Loot"]})
        except Exception: pass

        # 5. Fog of War
        fog_map = fog_service.get_fog_state()

        return {
            "system_status": status,
            "daily_budget": daily_budget,
            "party": party,
            "active_quests": active_quests,
            "fog_map": fog_map # New
        }

    except Exception as e:
        print(f"Error fetching game state: {e}")
        return {"error": str(e)}

def fetch_graph_nodes() -> Dict[str, Any]:
    """Fetch Cytoscape Graph Nodes (Last 20 Triples)."""
    try:
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o . } LIMIT 20"
        results = orch.query_graph(query)

        nodes = []
        edges = []
        node_ids = set()

        def add_node(uri_or_literal, node_type="unknown"):
            n_id = str(uri_or_literal).strip('<>"')
            label = n_id.split('/')[-1] if '/' in n_id else n_id
            if n_id not in node_ids:
                nodes.append({"data": { "id": n_id, "label": label, "type": node_type }})
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
                edges.append({"data": { "source": s_id, "target": o_id, "label": p_label }})

        return {"elements": {"nodes": nodes, "edges": edges}}
    except Exception as e:
        print(f"Error fetching graph nodes: {e}")
        return {"elements": {"nodes": [], "edges": []}}

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

# --- Godot Script Endpoints ---
@app.get("/api/v1/godot/scripts/agent")
async def get_agent_script(): return {"script": AGENT_UNIT_GD}

@app.get("/api/v1/godot/scripts/fog")
async def get_fog_script(): return {"script": FOG_MANAGER_GD}

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
        payload = {
            "type": "HARDENING_EVENT",
            "payload": event.dict()
        }
        await manager.broadcast(payload)
        return {"status": "broadcasted", "event": event}
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18789)
