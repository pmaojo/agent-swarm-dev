import asyncio
import json
import uuid
import time
from typing import Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, Request, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from agents.orchestrator import OrchestratorAgent

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
        # Ideally query Synapse for maxBudget
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

async def broadcast_stats_loop():
    """Background task to push stats."""
    while True:
        try:
            stats = await asyncio.to_thread(fetch_stats)
            if stats:
                await manager.broadcast({"type": "stats_update", "payload": stats})
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

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status")
async def get_status():
    """REST Endpoint for system status."""
    return await asyncio.to_thread(fetch_stats)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        # OpenClaw Protocol: Expect connect frame?
        # Or we can be lenient.
        # But for compatibility with dashboard, we wait for connect.
        try:
            initial_data = await websocket.receive_json()
        except Exception:
            # Client connected but sent nothing or garbage?
            # Just keep connection open for stats?
            # Or close?
            # OpenClaw spec is strict.
            await manager.disconnect(websocket)
            return

        if initial_data.get("method") == "connect":
            await websocket.send_json({
                "type": "hello-ok",
                "health": "ok",
                "version": "1.1.0-observability",
                "agents": list(orch.agents.keys())
            })

        # Main Loop
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
                    await websocket.send_json({
                        "status": "ok",
                        "id": req_id,
                        "payload": result
                    })
                except Exception as e:
                    await websocket.send_json({
                        "status": "error",
                        "id": req_id,
                        "error": str(e)
                    })

            elif method == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.post("/webhook/{channel}")
async def inbound_webhook(channel: str, request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Normalize data from different channels
    session_id = data.get("session_id") or data.get("sender_id") or str(uuid.uuid4())
    text = data.get("text") or data.get("message", {}).get("text")

    if not text:
         raise HTTPException(status_code=400, detail="No text found in message")

    msg_id = f"http://swarm.os/msg/{uuid.uuid4()}"
    session_uri = f"http://swarm.os/session/{session_id}"

    # Ingestamos el mensaje como una "Instrucción de Usuario" (usando tu memory.owl)
    # We use the 'default' namespace so the global autonomous loop can find it.
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
