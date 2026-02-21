#!/usr/bin/env python3
"""
Coder Agent - Code generation based on specifications and feedback.
Real implementation using LLM and Synapse Memory.
"""
import os
import json
import grpc
import sys
import time
from typing import Dict, Any, Optional, List

# Add path to lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from llm import LLMService

class CoderAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.namespace = "default"
        self.llm = LLMService()
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"❌ [Coder] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def query_critiques(self, task_description: str) -> List[str]:
        """Query Synapse for past critiques related to this task context."""
        if not self.stub: return []
        
        # In a real scenario, we'd link task instances.
        # For now, we search for ReviewCritiques that might be relevant or rely on the Orchestrator's loop.
        # But let's try to find any 'ReviewCritique' nodes.
        query = """
        SELECT ?message
        WHERE {
            ?critique <http://swarm.os/type> <http://swarm.os/ArtifactType> .
            ?critique <http://swarm.os/description> "Feedback from Reviewer explaining why code was rejected." .
            ?critique <http://swarm.os/hasProperty> ?prop .
            ?prop <http://swarm.os/message> ?message .
        }
        LIMIT 5
        """
        # This is a broad query. In a refined system, we would filter by Task ID.
        try:
            request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
            response = self.stub.QuerySparql(request)
            results = json.loads(response.results_json)
            return [r.get("message", "") for r in results if r.get("message")]
        except Exception as e:
            print(f"⚠️ [Coder] Failed to query critiques: {e}")
            return []

    def record_artifact(self, filename: str, content: str):
        """Record the generated artifact in Synapse."""
        if not self.stub: return

        subject = f"http://swarm.os/artifact/code/{int(time.time())}_{filename}"
        triples = [
            {"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/ArtifactType"},
            {"subject": subject, "predicate": "http://swarm.os/description", "object": "Generated Code"},
            {"subject": subject, "predicate": "http://swarm.os/hasProperty", "object": f"http://swarm.os/prop/path/{filename}"},
        ]

        # Properties
        # Ideally we ingest properties as separate nodes or literals if supported.
        # Synapse light supports basic triples.

        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
            print(f"💾 [Coder] Recorded artifact: {filename}")
        except Exception as e:
            print(f"⚠️ [Coder] Failed to record artifact: {e}")

    def generate_code(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Generate code using LLM."""

        # Fetch relevant context
        critiques = self.query_critiques(task)
        history = context.get('history', []) if context else []

        system_prompt = """
        You are an expert Python software engineer.
        Your task is to implement the requested feature.
        Return ONLY a JSON object with the following structure:
        {
            "files": [
                {
                    "path": "path/to/file.py",
                    "content": "full source code"
                }
            ],
            "dependencies": ["list", "of", "pip", "packages"]
        }
        Ensure code is complete, correct, and follows best practices.
        """

        prompt = f"Task: {task}\n"

        if history:
            prompt += "\nHistory of previous attempts:\n"
            for h in history:
                prompt += f"- {h.get('outcome')}: {json.dumps(h.get('result', {}).get('issues', []))}\n"

        if critiques:
            prompt += "\nRelevant Knowledge Base Critiques:\n"
            for c in critiques:
                prompt += f"- {c}\n"

        print(f"🧠 [Coder] Thinking... (Task: {task})")

        try:
            response = self.llm.get_structured_completion(prompt, system_prompt)
            return response
        except Exception as e:
            print(f"❌ [Coder] LLM generation failed: {e}")
            return {"files": [], "error": str(e)}

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        result = self.generate_code(task, context)

        generated_files = result.get("files", [])
        if not generated_files:
             return {"status": "failure", "issues": ["No code generated"]}

        # Write files to disk
        saved_files = []
        for file_data in generated_files:
            path = file_data.get("path")
            content = file_data.get("content")

            if path and content:
                # Ensure directory exists
                dir_path = os.path.dirname(path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path)

                with open(path, "w") as f:
                    f.write(content)

                saved_files.append(path)
                self.record_artifact(path, content)
                print(f"✍️ [Coder] Wrote file: {path}")

        return {
            "status": "success",
            "task": task,
            "generated": result,
            "saved_files": saved_files
        }

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Create a hello world python script"
    agent = CoderAgent()
    result = agent.run(task)
    print(json.dumps(result, indent=2))
