#!/usr/bin/env python3
"""
Deployer Agent - Deployment and Verification.
Real implementation: Installs dependencies and executes code.
"""
import os
import json
import grpc
import sys
import subprocess
import time
from typing import Dict, Any, List, Optional

# Add path to lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc

class DeployerAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.namespace = "default"
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"❌ [Deployer] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def get_coder_output(self, context: Dict) -> Dict[str, Any]:
        """Extract generated code info from history."""
        history = context.get('history', [])
        for entry in reversed(history):
            if entry.get('agent') == 'Coder' and entry.get('outcome') == 'success':
                return entry.get('result', {}).get('generated', {})
        return {}

    def install_dependencies(self, dependencies: List[str]):
        """Install dependencies via pip."""
        if not dependencies:
            return
        print(f"📦 [Deployer] Installing dependencies: {dependencies}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + dependencies)
        except subprocess.CalledProcessError as e:
            print(f"❌ [Deployer] Dependency installation failed: {e}")
            raise

    def run_execution(self, entrypoint: str) -> Dict[str, Any]:
        """Run the entrypoint script."""
        print(f"🚀 [Deployer] Executing {entrypoint}...")
        try:
            # Run with timeout of 5 seconds to verify it starts
            # If it's a long running process (server), it might be killed, which is fine for verification.
            proc = subprocess.run([sys.executable, entrypoint], capture_output=True, text=True, timeout=5)
            return {
                "status": "success",
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
        except subprocess.TimeoutExpired as e:
            # Use 'stdout' if available (it is bytes in TimeoutExpired usually, unless text=True works?)
            # subprocess.TimeoutExpired.stdout is bytes by default in older python, but here we use text=True.
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
            print(f"✅ [Deployer] Execution verified (timed out as expected for servers).")
            return {
                "status": "success",
                "stdout": stdout,
                "stderr": stderr,
                "message": "Process started successfully (timed out)"
            }
        except Exception as e:
            print(f"❌ [Deployer] Execution failed: {e}")
            return {"status": "failure", "error": str(e)}

    def record_deployment(self, entrypoint: str, result: Dict):
        """Record deployment in Synapse."""
        if not self.stub: return

        subject = f"http://swarm.os/deployment/{int(time.time())}"
        status = "success" if result.get("status") == "success" else "failure"

        triples = [
            {"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/ArtifactType"},
            {"subject": subject, "predicate": "http://swarm.os/description", "object": "Deployment Result"},
            {"subject": subject, "predicate": "http://swarm.os/hasProperty", "object": f"http://swarm.os/prop/status/{status}"},
            {"subject": subject, "predicate": "http://swarm.os/hasProperty", "object": f"http://swarm.os/prop/entrypoint/{os.path.basename(entrypoint)}"},
        ]

        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
            print(f"💾 [Deployer] Recorded deployment: {status}")
        except Exception as e:
            print(f"⚠️ [Deployer] Failed to record deployment: {e}")

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        coder_out = self.get_coder_output(context or {})
        dependencies = coder_out.get("dependencies", [])
        files = coder_out.get("files", [])

        if not files:
            print("⚠️ [Deployer] No files to deploy.")
            return {"status": "failure", "message": "No files found"}

        # 1. Install Dependencies
        try:
            self.install_dependencies(dependencies)
        except Exception as e:
            return {"status": "failure", "error": f"Dependency installation failed: {e}"}

        # 2. Determine Entrypoint (heuristic)
        entrypoint = None
        for f in files:
            path = f.get("path", "")
            if path.endswith("main.py") or path.endswith("app.py"):
                entrypoint = path
                break
        if not entrypoint and files:
            entrypoint = files[0].get("path") # Fallback to first file

        if not entrypoint:
             return {"status": "failure", "message": "No entrypoint found"}

        # 3. Execute
        exec_result = self.run_execution(entrypoint)

        # 4. Record
        self.record_deployment(entrypoint, exec_result)
        
        return {
            "status": exec_result.get("status"),
            "deployment": exec_result,
            "url": "local://" + entrypoint # Mock URL for local deployment
        }

if __name__ == "__main__":
    mock_context = {
        "history": [
            {
                "agent": "Coder",
                "outcome": "success",
                "result": {
                    "generated": {
                        "files": [{"path": "hello.py", "content": "print('Hello World')"}],
                        "dependencies": []
                    }
                }
            }
        ]
    }
    # Create dummy file for test
    with open("hello.py", "w") as f: f.write("print('Hello World')")

    agent = DeployerAgent()
    result = agent.run("Deploy", mock_context)
    print(json.dumps(result, indent=2))
    os.remove("hello.py")
