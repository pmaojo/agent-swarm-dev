#!/usr/bin/env python3
"""
Reviewer Agent - Code quality and security review.
Real implementation using Static Analysis + LLM + Synapse Memory + Neurosymbolic Verification.
"""
import os
import json
import requests
import grpc
import sys
import time
from typing import Dict, Any, List, Optional

# Add path to lib and root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Add path to proto for generated code imports
proto_dir = os.path.join(os.path.dirname(__file__), 'proto')
if proto_dir not in sys.path:
    sys.path.insert(0, proto_dir)

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from llm import LLMService
from git_service import GitService
from agents.tools.shell import execute_command
from agents.tools.api_sandbox import ApiSandboxTool

SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

class ReviewerAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.namespace = "default"
        self.llm = LLMService()
        self.git = GitService()
        self.sandbox_tool = ApiSandboxTool()
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

    def _query(self, query: str) -> List[Dict]:
        if not self.stub: return []
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
        try:
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception: return []

    def _ingest(self, triples: List[Dict[str, str]]):
        if not self.stub: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
        except Exception as e:
            print(f"⚠️ Ingest failed: {e}")

    def verify_pr_compliance(self, branch_name: str) -> Dict[str, Any]:
        """
        Neurosymbolic Verification:
        1. Fetch semantics (Task -> Spec -> Requirements)
        2. Fetch constraints (NIST HardConstraints)
        3. Analyze Diff (GitService)
        4. LLM Reasoning (Violations?)
        """
        print(f"⚖️  Verifying Semantic Compliance for {branch_name}...")

        # 1. Fetch Requirements via Lineage
        # <branch> swarm:originatesFrom ?task . ?task swarm:hasSpec ?spec . ?spec swarm:requirement ?req
        branch_uri = f"{SWARM}branch/{branch_name}"
        query_reqs = f"""
        PREFIX swarm: <{SWARM}>
        SELECT ?requirement
        WHERE {{
            <{branch_uri}> swarm:originatesFrom ?task .
            ?task swarm:hasSpec ?spec .
            ?spec swarm:requirement ?requirement .
        }}
        """
        req_results = self._query(query_reqs)
        requirements = [r.get("?requirement") or r.get("requirement") for r in req_results]

        # 2. Fetch Hard Constraints (Global & Contextual)
        # Assuming we check all active HardConstraints or filter by stack if known
        query_constraints = f"""
        PREFIX nist: <{NIST}>
        SELECT ?constraint WHERE {{ ?s nist:HardConstraint ?constraint }}
        """
        const_results = self._query(query_constraints)
        constraints = [r.get("?constraint") or r.get("constraint") for r in const_results]

        # 3. Get Diff
        diff = self.git.get_diff(branch_name)
        if not diff:
            print("⚠️ No diff found (or branch empty).")
            # If no diff, technically compliant but suspicious?
            # Let's verify file existence?
            pass

        # 4. LLM Reasoning
        if not requirements and not constraints:
            print("ℹ️  No semantic requirements found. Skipping Deep Verification.")
            return {"compliant": True, "reason": "No requirements found"}

        system_prompt = """
        You are a Neurosymbolic Verification Engine (OWL-RL Simulator).
        Analyze the Git Diff against the provided Hard Constraints and Requirements.

        Output JSON:
        {
            "compliant": boolean,
            "violations": ["list of strings"],
            "reasoning": "summary"
        }
        """

        prompt = f"""
        Requirements:
        {json.dumps(requirements, indent=2)}

        Hard Constraints (NIST):
        {json.dumps(constraints, indent=2)}

        Git Diff:
        {diff[:5000]} (Truncated if too long)
        """

        try:
            analysis = self.llm.get_structured_completion(prompt, system_prompt)

            if analysis.get("compliant"):
                print("✅ Neurosymbolic Verification Passed.")
                # Ingest Approval
                # <agent:Reviewer> swarm:approved <branch:URI>
                self._ingest([{
                    "subject": f"{SWARM}agent/Reviewer",
                    "predicate": f"{SWARM}approved",
                    "object": f"<{branch_uri}>" # Object property
                }])
            else:
                print(f"⛔ Verification Failed: {analysis.get('violations')}")

            return analysis

        except Exception as e:
            print(f"❌ Verification Logic Failed: {e}")
            return {"compliant": False, "error": str(e)}

    def broadcast_hardening_event(self, event_type: str, message: str, details: Dict):
        try:
            requests.post("http://localhost:18789/api/v1/events/hardening", json={
                "type": event_type,
                "message": message,
                "severity": "CRITICAL" if event_type == "CONTRACT_FAILURE" else "WARNING",
                "details": details
            }, timeout=2)
        except: pass

    def run_contract_tests(self, context: Dict) -> Dict[str, Any]:
        """
        Executes tests against the Apicentric Mock.
        """
        print("🛡️  Starting Contract Tests (Apicentric)...")

        # 1. Identify OpenAPI Spec
        spec_content = None
        service_name = "unknown-service"

        # Try to find openapi.yaml in the repo
        potential_specs = [f for f in os.listdir(".") if f.endswith("openapi.yaml") or f.endswith("swagger.yaml")]
        # Also check openspec/
        if os.path.exists("openspec"):
            potential_specs.extend([os.path.join("openspec", f) for f in os.listdir("openspec") if f.endswith(".yaml")])

        if potential_specs:
            # Pick the first one for now
            fname = potential_specs[0]
            try:
                with open(fname, "r") as f:
                    spec_content = f.read()
                service_name = os.path.basename(fname).replace(".yaml", "").replace(".json", "")
            except Exception as e:
                print(f"⚠️ Failed to read spec {fname}: {e}")

        if not spec_content:
            print("⚠️  No OpenAPI spec found. Skipping Contract Tests.")
            return {"status": "skipped", "reason": "No spec found"}

        # 2. Start Sandbox
        try:
            mock_url = self.sandbox_tool.create_sandbox(spec_content, service_name)
            if "Error" in mock_url:
                raise Exception(mock_url)
        except Exception as e:
            print(f"❌ Failed to start sandbox: {e}")
            return {"status": "error", "error": str(e)}

        # 3. Run Tests with BASE_URL
        print(f"🧪 Running tests against Mock: {mock_url}")

        cmd = "pytest tests/ --maxfail=5" # Fail fast

        try:
            result = execute_command(cmd, reason="Contract Testing", env={"BASE_URL": mock_url})
            if result.get('status') == 'success':
                print("✅ Contract Tests Passed.")
                return {"status": "success"}
            else:
                print("⛔ Contract Tests Failed!")
                # Broadcast Hardening Event
                self.broadcast_hardening_event("CONTRACT_FAILURE", f"Tests failed against {mock_url}", {"stdout": result.get('stdout'), "stderr": result.get('stderr')})
                return {"status": "failure", "output": result.get('stdout')}
        except Exception as e:
             print(f"❌ Test execution error: {e}")
             return {"status": "error", "error": str(e)}

    def get_files_to_review(self, context: Dict) -> List[str]:
        """Extract file paths from previous Coder output in history."""
        history = context.get('history', [])
        if not history:
            return []
        for entry in reversed(history):
            if entry.get('agent') == 'Coder' and entry.get('outcome') == 'success':
                files = entry.get('result', {}).get('saved_files', [])
                if files: return files
        return []

    def run_static_analysis(self, files: List[str]) -> Dict[str, Any]:
        results = {}
        for file_path in files:
            if not os.path.exists(file_path): continue
            file_results = {"pylint": [], "flake8": [], "bandit": []}

            # Pylint
            try:
                cmd = f"pylint --output-format=json {file_path}"
                res = execute_command(cmd, reason="Static Analysis")
                if res.get("stdout"):
                    try:
                        file_results["pylint"] = json.loads(res.get("stdout"))
                    except json.JSONDecodeError:
                         print(f"⚠️ Failed to parse pylint output for {file_path}")
            except Exception as e:
                print(f"⚠️ Pylint execution failed for {file_path}: {e}")

            # Flake8
            try:
                cmd = f"flake8 --format=default {file_path}"
                res = execute_command(cmd, reason="Static Analysis")
                if res.get("stdout"):
                     lines = res.get("stdout").splitlines()
                     file_results["flake8"] = lines
            except Exception as e:
                 print(f"⚠️ Flake8 execution failed for {file_path}: {e}")

            # Bandit
            try:
                cmd = f"bandit -f json -r {file_path}"
                res = execute_command(cmd, reason="Static Analysis")
                if res.get("stdout"):
                    try:
                        file_results["bandit"] = json.loads(res.get("stdout")).get("results", [])
                    except json.JSONDecodeError:
                         print(f"⚠️ Failed to parse bandit output for {file_path}")
            except Exception as e:
                 print(f"⚠️ Bandit execution failed for {file_path}: {e}")

            results[file_path] = file_results
        return results

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        # 1. Semantic Compliance (New Feature)
        branch_name = self.git.get_current_branch()
        compliance = self.verify_pr_compliance(branch_name)

        if not compliance.get("compliant", True):
             return {
                 "status": "failure",
                 "error": "Semantic Verification Failed",
                 "violations": compliance.get("violations")
             }

        # 2. Mandatory Contract Testing (Apicentric)
        contract_results = self.run_contract_tests(context or {})
        if contract_results.get("status") == "failure":
             return {
                 "status": "failure",
                 "error": "CONTRACT_VIOLATION",
                 "violations": ["Contract Tests Failed against Apicentric Mock"],
                 "details": contract_results
             }

        # 3. Traditional Review (Files)
        files = self.get_files_to_review(context or {})
        static_analysis_results = self.run_static_analysis(files)

        # 4. LLM Code Review
        # Consolidated feedback from Static Analysis + LLM
        review_summary = "Review Passed."
        if static_analysis_results:
            has_issues = False
            for f, res in static_analysis_results.items():
                if res.get("pylint") or res.get("flake8") or res.get("bandit"):
                    has_issues = True
                    # Broadcast Static Analysis Failure
                    self.broadcast_hardening_event("STATIC_ANALYSIS", f"Issues found in {f}", {"pylint": res.get("pylint"), "bandit": res.get("bandit")})
                    break

            if has_issues:
                review_summary = "Static Analysis found issues. Check logs."

        return {
            "status": "success",
            "message": review_summary,
            "compliance": compliance,
            "static_analysis": static_analysis_results
        }

if __name__ == "__main__":
    agent = ReviewerAgent()
    print(agent.run("Verify PR"))
