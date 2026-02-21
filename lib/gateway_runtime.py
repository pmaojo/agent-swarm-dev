import asyncio
import json
import uuid
import time
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agents.orchestrator import OrchestratorAgent

app = FastAPI()

# Enable CORS
# Using wildcard allow_origins with allow_credentials=True is insecure and disallowed by some browsers.
# For development, we can allow localhost or specific domains.
# Or, if we need truly open access (e.g. for TUI/Web running anywhere), we disable credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Changed to False for wildcard origin security
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Orchestrator instance
# We use this for both direct WebSocket execution and for ingesting Webhook tasks.
orch = OrchestratorAgent()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # Simulación del protocolo OpenClaw: Primer frame debe ser 'connect'
        try:
            initial_data = await websocket.receive_json()
        except Exception:
            await websocket.close(code=4000)
            return

        if initial_data.get("method") != "connect":
            # If not connect, strictly speaking we should fail, but for robustness we might log it.
            # OpenClaw spec says first frame MUST be connect.
            await websocket.close(code=4000, reason="First frame must be connect")
            return

        # Responder con hello-ok (Snapshot del sistema)
        await websocket.send_json({
            "type": "hello-ok",
            "health": "ok",
            "version": "1.0.0-synapse",
            "agents": list(orch.agents.keys())
        })

        # Loop de mensajes (Async para no bloquear el Orchestrator)
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

                # Ejecución en dos etapas (como OpenClaw)
                await websocket.send_json({"status": "accepted", "id": req_id})

                # El Orchestrator procesa
                # Note: This runs the task directly on this connection.
                # Ideally we would stream events here. For now, we wait for full result.
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

    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

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
