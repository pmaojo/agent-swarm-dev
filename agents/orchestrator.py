#!/usr/bin/env python3
"""
Orchestrator Agent - Task decomposition and workflow management
"""
import os
import json
import grpc
import sys
import yaml
import time
from typing import List, Dict, Any, Optional

# Add path to synapse sdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc

class OrchestratorAgent:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.grpc_host = "localhost"
        self.grpc_port = 50051
        self.channel = None
        self.stub = None
        self.namespace = "default"

        # Connect to Synapse
        self.connect()
        
        # Load Schema at startup
        self.load_schema()

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
            # Simple ping/check if server is up
            try:
                grpc.channel_ready_future(self.channel).result(timeout=2)
                print("✅ Connected to Synapse")
            except grpc.FutureTimeoutError:
                print("⚠️  Synapse not reachable. Is it running?")
        except Exception as e:
            print(f"❌ Failed to connect to Synapse: {e}")

    def ingest_triples(self, triples: List[Dict[str, str]], namespace: str = "default"):
        """Ingest triples helper"""
        if not self.stub: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(
            triples=pb_triples,
            namespace=namespace
        )
        self.stub.IngestTriples(request)

    def load_schema(self):
        """Load swarm_schema.yaml into Synapse"""
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'swarm_schema.yaml')
        if not os.path.exists(schema_path):
            print(f"⚠️  Schema file not found at {schema_path}")
            return

        print("📥 Loading Swarm Schema...")
        try:
            with open(schema_path, 'r') as f:
                schema = yaml.safe_load(f)

            triples = []
            # Agents
            for agent_name, agent_data in schema.get('agents', {}).items():
                subject = f"http://swarm.os/agent/{agent_name}"
                triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/Agent"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": agent_data.get('description', '')})

            # Tasks
            for task_name, task_data in schema.get('tasks', {}).items():
                subject = f"http://swarm.os/task/{task_name}"
                triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/TaskType"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/handler", "object": f"http://swarm.os/agent/{task_data.get('handler')}"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": task_data.get('description', '')})

            # Transitions
            for task_name, transitions in schema.get('transitions', {}).items():
                subject = f"http://swarm.os/task/{task_name}"
                if transitions.get('on_success'):
                    triples.append({"subject": subject, "predicate": "http://swarm.os/on_success", "object": f"http://swarm.os/task/{transitions.get('on_success')}"})
                if transitions.get('on_failure'):
                    triples.append({"subject": subject, "predicate": "http://swarm.os/on_failure", "object": f"http://swarm.os/task/{transitions.get('on_failure')}"})

            self.ingest_triples(triples, namespace=self.namespace)
            print(f"✅ Schema loaded ({len(triples)} triples)")
        except Exception as e:
            print(f"❌ Failed to load schema: {e}")

    def query_graph(self, query: str) -> List[Dict]:
        """Execute SPARQL query against Synapse"""
        if not self.stub:
            print("❌ Not connected to Synapse")
            return []

        request = semantic_engine_pb2.SparqlRequest(
            query=query,
            namespace=self.namespace
        )
        try:
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception as e:
            print(f"❌ Graph query failed: {e}")
            return []

    def get_initial_task_type(self, task_description: str) -> str:
        """Determine initial task type based on description or default to FeatureImplementationTask"""
        # For now, default to FeatureImplementationTask as per schema for development tasks
        return "FeatureImplementationTask"

    def get_handler_for_task(self, task_type: str) -> str:
        """Query graph to find handler for task type"""
        query = f"""
        SELECT ?agentUri
        WHERE {{
            <http://swarm.os/task/{task_type}> <http://swarm.os/handler> ?agentUri .
        }}
        """
        results = self.query_graph(query)

        if results and len(results) > 0:
            agent_uri = results[0].get("?agentUri") or results[0].get("agentUri")
            if agent_uri:
                return agent_uri.strip("<>").split("/")[-1]
        return "Unknown"

    def get_next_task(self, current_task_type: str, outcome: str) -> Optional[str]:
        """Query graph for next task based on outcome"""
        predicate = "on_success" if outcome == "success" else "on_failure"
        query = f"""
        SELECT ?nextTaskUri
        WHERE {{
            <http://swarm.os/task/{current_task_type}> <http://swarm.os/{predicate}> ?nextTaskUri .
        }}
        """
        results = self.query_graph(query)
        if results and len(results) > 0:
            next_task_uri = results[0].get("?nextTaskUri") or results[0].get("nextTaskUri")
            if next_task_uri:
                return next_task_uri.strip("<>").split("/")[-1]
        return None

    def run_agent(self, agent_name: str, task_desc: str, context: Dict = None) -> Dict:
        """Execute an agent (mock execution for now)"""
        print(f"🤖 Agent '{agent_name}' executing: {task_desc}")

        # Simulate agent execution
        if agent_name == "Coder":
            return {"status": "success", "generated": {"files": ["app.py"]}}
        elif agent_name == "Reviewer":
            # Simulate failure if context says so, or random/default success
            if "buggy" in task_desc.lower() and "Fix previous issues" not in task_desc:
                print("❌ Reviewer rejected the code!")
                return {"status": "failure", "issues": ["Syntax error"]}
            print("✅ Reviewer approved the code.")
            return {"status": "success"}
        elif agent_name == "Deployer":
            return {"status": "success", "url": "https://vercel.app/project"}

        return {"status": "success"}

    def run(self, task: str) -> Dict[str, Any]:
        print(f"🚀 Orchestrator starting task: {task}")
        
        # 1. Determine Initial State
        current_task_type = self.get_initial_task_type(task)
        history = []
        
        while current_task_type:
            # 2. Find Responsible Agent
            agent_name = self.get_handler_for_task(current_task_type)
            print(f"📍 Step: {current_task_type} -> Handler: {agent_name}")

            if agent_name == "Unknown":
                print(f"❌ No handler found for {current_task_type}")
                break

            # 3. Execute Agent
            result = self.run_agent(agent_name, task, {"history": history})
            outcome = result.get("status", "failure")

            history.append({
                "task_type": current_task_type,
                "agent": agent_name,
                "result": result,
                "outcome": outcome
            })

            # 4. Determine Next Step (Reasoning)
            next_task_type = self.get_next_task(current_task_type, outcome)

            if next_task_type:
                print(f"🔄 Transition: {current_task_type} ({outcome}) -> {next_task_type}")

                if outcome == "failure":
                     print("⚠️  Task failed... appending feedback to instructions.")
                     issues = result.get('issues', ['Unknown error'])
                     task = f"{task} (Fix previous issues: {issues})"

                current_task_type = next_task_type
            else:
                print("🏁 Workflow Complete")
                break

        return {
            "task": task,
            "history": history,
            "final_status": "success" if history and history[-1]["outcome"] == "success" else "failure"
        }

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Implement feature X"
    agent = OrchestratorAgent()
    result = agent.run(task)
    print(json.dumps(result, indent=2))
