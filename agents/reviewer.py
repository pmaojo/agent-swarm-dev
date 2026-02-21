#!/usr/bin/env python3
"""
Reviewer Agent - Code quality and security review.
Real implementation using Static Analysis + LLM + Synapse Memory.
"""
import os
import json
import grpc
import sys
import time
from typing import Dict, Any, List, Optional

# Add path to lib and root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from llm import LLMService
from agents.tools.shell import execute_command

class ReviewerAgent:
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
            print(f"❌ [Reviewer] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def get_files_to_review(self, context: Dict) -> List[str]:
        """Extract file paths from previous Coder output in history."""
        history = context.get('history', [])
        if not history:
            return []
        
        # Look for the last successful Coder task
        for entry in reversed(history):
            if entry.get('agent') == 'Coder' and entry.get('outcome') == 'success':
                return entry.get('result', {}).get('saved_files', [])
        return []

    def run_static_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run pylint, flake8, bandit on files using CommandGuard."""
        results = {}
        for file_path in files:
            if not os.path.exists(file_path):
                continue

            file_results = {"pylint": [], "flake8": [], "bandit": []}

            # Pylint
            try:
                cmd = f"pylint --output-format=json {file_path}"
                res = execute_command(cmd, reason="Static Code Analysis")
                if res.get("stdout"):
                    try:
                        file_results["pylint"] = json.loads(res.get("stdout"))
                    except json.JSONDecodeError:
                        file_results["pylint"] = [{"message": "Failed to parse pylint output", "raw": res.get("stdout")}]
                elif res.get("status") == "failure":
                     file_results["pylint"] = [{"error": res.get("error")}]
            except Exception as e:
                file_results["pylint"] = [{"error": str(e)}]

            # Flake8
            try:
                cmd = f"flake8 --format=default {file_path}"
                res = execute_command(cmd, reason="Static Code Analysis")
                if res.get("stdout"):
                    # Flake8 default format is: file:line:col: code message
                    file_results["flake8"] = [{"raw": line} for line in res.get("stdout").splitlines() if line]
                elif res.get("status") == "failure":
                     file_results["flake8"] = [{"error": res.get("error")}]
            except Exception as e:
                file_results["flake8"] = [{"error": str(e)}]

            # Bandit (Security)
            try:
                cmd = f"bandit -f json -r {file_path}"
                res = execute_command(cmd, reason="Static Code Analysis")
                if res.get("stdout"):
                     try:
                        file_results["bandit"] = json.loads(res.get("stdout")).get("results", [])
                     except json.JSONDecodeError:
                        file_results["bandit"] = [{"message": "Failed to parse bandit output"}]
                elif res.get("status") == "failure":
                     file_results["bandit"] = [{"error": res.get("error")}]
            except Exception as e:
                 file_results["bandit"] = [{"error": str(e)}]

            results[file_path] = file_results

        return results

    def record_critique(self, file_path: str, issues: List[Dict]):
        """Store critique in Synapse."""
        if not self.stub: return

        subject = f"http://swarm.os/critique/{int(time.time())}_{os.path.basename(file_path)}"
        triples = [
            {"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/ArtifactType"},
            {"subject": subject, "predicate": "http://swarm.os/description", "object": "Feedback from Reviewer explaining why code was rejected."},
            {"subject": subject, "predicate": "http://swarm.os/hasProperty", "object": f"http://swarm.os/prop/file/{file_path}"},
        ]

        # Serialize issues to JSON string for the message property
        message = json.dumps(issues)
        prop_subj = f"http://swarm.os/prop/message/{int(time.time())}"
        triples.append({"subject": subject, "predicate": "http://swarm.os/hasProperty", "object": prop_subj})
        triples.append({"subject": prop_subj, "predicate": "http://swarm.os/message", "object": message})

        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
            print(f"💾 [Reviewer] Recorded critique for {file_path}")
        except Exception as e:
            print(f"⚠️ [Reviewer] Failed to record critique: {e}")

    def review_code(self, files: List[str], static_analysis: Dict) -> Dict[str, Any]:
        """Use LLM to review code, considering static analysis."""

        system_prompt = """
        You are a Senior Code Reviewer.
        Analyze the code for logical errors, security vulnerabilities, and best practices.
        You are provided with Static Analysis results (Pylint, Flake8, Bandit).

        Return a JSON object:
        {
            "status": "approved" | "rejected",
            "score": 0-100,
            "issues": [
                {
                    "file": "filename",
                    "line": 10,
                    "severity": "high" | "medium" | "low",
                    "message": "description of issue"
                }
            ],
            "summary": "Overall feedback"
        }
        If critical issues (security, syntax, logic) exist, status MUST be "rejected".
        """

        prompt = "Files to review:\n"
        for f in files:
            if os.path.exists(f):
                with open(f, 'r') as file:
                    prompt += f"\n--- {f} ---\n{file.read()}\n"

        prompt += "\nStatic Analysis Results:\n"
        prompt += json.dumps(static_analysis, indent=2)

        print(f"🧠 [Reviewer] analyzing {len(files)} files...")

        try:
            response = self.llm.get_structured_completion(prompt, system_prompt)
            return response
        except Exception as e:
            print(f"❌ [Reviewer] LLM review failed: {e}")
            return {"status": "rejected", "issues": [{"message": f"LLM Error: {e}"}]}

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        files = self.get_files_to_review(context or {})
        if not files:
            print("⚠️ [Reviewer] No files found to review in context.")
            return {"status": "success", "message": "No files to review (maybe first run?)"}

        # 1. Static Analysis
        static_results = self.run_static_analysis(files)

        # 2. LLM Review
        review_result = self.review_code(files, static_results)

        # 3. Record in Synapse
        if review_result.get("status") == "rejected":
             for issue in review_result.get("issues", []):
                 self.record_critique(issue.get("file", "unknown"), [issue])

        # Merge static analysis results into return value
        review_result["static_analysis"] = static_results

        return {
            "status": "success" if review_result.get("status") == "approved" else "failure",
            "review": review_result,
            "issues": [i.get("message") for i in review_result.get("issues", [])]
        }

if __name__ == "__main__":
    # Mock context for standalone run
    mock_context = {
        "history": [
            {
                "agent": "Coder",
                "outcome": "success",
                "result": {"saved_files": ["agents/coder.py"]} # Self-review!
            }
        ]
    }
    agent = ReviewerAgent()
    result = agent.run("Review the coder agent", mock_context)
    print(json.dumps(result, indent=2))
