#!/usr/bin/env python3
"""
Analyst Agent - Consolidates failure patterns into Golden Rules.
"""
import os
import sys
import json
import grpc
import yaml
import uuid
from collections import defaultdict
from typing import List, Dict, Any, Optional

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    from synapse_proto import orchestration_engine_pb2, orchestration_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    from agents.synapse_proto import orchestration_engine_pb2, orchestration_engine_pb2_grpc

from llm import LLMService
from orchestrator import OrchestratorAgent

import re

# Define Strict Namespaces
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
PROV = "http://www.w3.org/ns/prov#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS = "http://www.w3.org/2004/02/skos/core#"

# Pre-compiled regex for optimize_prompt performance
_LEADING_WS_RE = re.compile(r'^([ \t]*)')
_MULTI_SPACE_RE = re.compile(r' {2,}')
_MULTI_NEWLINE_RE = re.compile(r'\n{3,}')

class AnalystAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.namespace = "default"
        self.llm = LLMService()
        self.channel = None
        self.stub = None

        # New Rust microservice for Analyst logic
        self.analyst_channel = None
        self.analyst_stub = None

        self.connect()
        self.connect_analyst_service()
        self.config = self.load_config()
        self.threshold = self.config.get('memory_settings', {}).get('consolidation_threshold', 5)
        self.mock_llm = os.getenv("MOCK_LLM", "false").lower() == "true"
        self.sanity_suite = self.load_sanity_suite()

    def connect_analyst_service(self):
        """Connect to the new Rust-based Analyst microservice."""
        try:
            self.analyst_channel = grpc.insecure_channel("localhost:50055")
            self.analyst_stub = orchestration_engine_pb2_grpc.AnalystServiceStub(self.analyst_channel)
            print("✅ Analyst connected to Rust microservice stub at localhost:50055")
        except Exception as e:
            print(f"⚠️ Error initializing Rust Analyst microservice stub: {e}. Falling back to legacy Python logic.")
            self.analyst_stub = None

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
            # Check connection
            try:
                grpc.channel_ready_future(self.channel).result(timeout=2)
                print(f"✅ Analyst connected to Synapse at {self.grpc_host}:{self.grpc_port}")
            except grpc.FutureTimeoutError:
                print("⚠️  Synapse not reachable. Is it running?")
        except Exception as e:
            print(f"❌ Failed to connect to Synapse: {e}")

    def load_config(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'swarm_schema.yaml')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def load_sanity_suite(self):
        suite_path = os.path.join(os.path.dirname(__file__), '..', 'scenarios', 'sanity_suite.yaml')
        if os.path.exists(suite_path):
            with open(suite_path, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def query_graph(self, query: str) -> List[Dict]:
        if not self.stub: return []
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
        try:
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception as e:
            print(f"❌ SPARQL Query failed: {e}")
            return []

    def ingest_triples(self, triples: List[Dict[str, str]]):
        if not self.stub: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace)
        self.stub.IngestTriples(request)

    def find_unconsolidated_failures(self):
        # Strict Namespace Query with Literal Matching
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX nist: <{NIST}>
        PREFIX prov: <{PROV}>
        PREFIX rdf: <{RDF}>
        PREFIX skos: <{SKOS}>

        SELECT ?execId ?agent ?role ?note ?stack
        WHERE {{
            ?execId rdf:type swarm:ExecutionRecord .
            ?execId nist:resultState "on_failure" .
            ?execId prov:wasAssociatedWith ?agent .
            ?agent rdf:type ?role .
            ?execId skos:historyNote ?note .

            OPTIONAL {{ ?execId swarm:hasStack ?stack }}

            FILTER NOT EXISTS {{ ?execId swarm:isConsolidated "true" }}
        }}
        """
        return self.query_graph(query)

    def cluster_failures(self, failures):
        if self.analyst_stub is not None:
            try:
                failure_infos = []
                for f in failures:
                    exec_id = f.get("?execId", f.get("execId", ""))
                    note = f.get("?note", f.get("note", ""))
                    role = f.get("?role", f.get("role", ""))
                    stack = f.get("?stack", f.get("stack", "python"))

                    if isinstance(exec_id, dict): exec_id = exec_id.get('value', '')
                    if isinstance(note, dict): note = note.get('value', '')
                    if isinstance(role, dict): role = role.get('value', '')
                    if isinstance(stack, dict): stack = stack.get('value', 'python')

                    failure_infos.append(orchestration_engine_pb2.FailureInfo(
                        exec_id=str(exec_id), note=str(note), role=str(role), stack=str(stack)
                    ))

                request = orchestration_engine_pb2.ClusterRequest(failures=failure_infos)
                response = self.analyst_stub.ClusterFailures(request, timeout=2.0)
                if response.json_clusters and response.json_clusters != "{}":
                    try:
                        return json.loads(response.json_clusters)
                    except json.JSONDecodeError:
                        pass
            except grpc.RpcError:
                pass
            except Exception as e:
                print(f"⚠️ Error clustering via Rust microservice: {e}. Falling back to Python.")

        clusters = defaultdict(list)
        decoder = json.JSONDecoder()

        for f in failures:
            role = f.get('role') or f.get('?role')
            note = f.get('note') or f.get('?note')
            execId = f.get('execId') or f.get('?execId')
            stack = f.get('stack') or f.get('?stack') or "unknown"

            # Note is a literal, check if it's a JSON string
            if isinstance(note, dict):
                note = note.get('value', '')

            # Stack might be a dict if it came from JSON results with type info
            if isinstance(stack, dict):
                stack = stack.get('value', 'unknown')

            # Role might be a dict (URI)
            if isinstance(role, dict):
                role = role.get('value', '')

            try:
                # Remove surrounding quotes from JSON string if double-encoded
                if note.startswith('"') and note.endswith('"') and len(note) > 1:
                     note = note[1:-1]

                # Stack usually comes as "python" (quoted)
                if stack.startswith('"') and stack.endswith('"'):
                    stack = stack[1:-1]

                # @synapse:optimization Use raw_decode to avoid full parsing of large log arrays
                # @synapse:fix Ensure note is hashable (handle nested lists/dicts)
                if note.startswith('[') and note.endswith(']'):
                   try:
                       # Skip the opening bracket '[' at index 0, start parsing at index 1
                       parsed_val, _ = decoder.raw_decode(note, 1)

                       # If valid parsed value, use it.
                       # Ensure it's hashable for clustering keys.
                       if isinstance(parsed_val, (list, dict)):
                           note = str(parsed_val)
                       else:
                           note = parsed_val
                   except json.JSONDecodeError:
                       pass
            except:
                pass

            # Cluster by (Role, Note, Stack)
            key = (role, note, stack)
            clusters[key].append(execId)
        return clusters

    def optimize_prompt(self, prompt: str) -> str:
        """
        Reduces token usage before LLM submission by safely collapsing redundant
        inline spaces and excessive newlines while preserving indentation to avoid
        corrupting code or stack traces.
        """
        # @synapse:rule Optimize prompts before LLM submission to conserve tokens while preserving code formatting.
        # @synapse:constraint Compile regular expressions at the module level to avoid compiling them in hot paths.
        if self.analyst_stub is not None:
            try:
                request = orchestrator_pb2.OptimizePromptRequest(prompt=prompt)
                response = self.analyst_stub.OptimizePrompt(request, timeout=1.0)
                return response.optimized_prompt
            except grpc.RpcError as e:
                pass
            except Exception as e:
                print(f"⚠️ Error in Rust Analyst microservice OptimizePrompt, falling back to legacy Python: {e}")

        # Collapse multiple spaces into one, but preserve leading spaces (indentation)
        lines = prompt.split('\n')
        optimized_lines = []
        for line in lines:
            # Match leading whitespace (spaces and tabs)
            match = _LEADING_WS_RE.match(line)
            leading_whitespace = match.group(1) if match else ''

            # Collapse spaces in the rest of the line
            rest_of_line = line[len(leading_whitespace):]
            content = _MULTI_SPACE_RE.sub(' ', rest_of_line)
            optimized_lines.append(leading_whitespace + content)

        # Rejoin and collapse 3+ newlines into 2
        optimized = '\n'.join(optimized_lines)
        return _MULTI_NEWLINE_RE.sub('\n\n', optimized).strip()

    def generate_golden_rule(self, role, note, count, stack):
        # Clean Role for Prompt (it's a URI)
        role_name = role.split('/')[-1]

        if self.analyst_stub is not None:
            try:
                request = orchestration_engine_pb2.RuleRequest(role=role_name, note=note, count=count, stack=stack)
                response = self.analyst_stub.GenerateGoldenRules(request, timeout=3.0)
                if response.rule:
                    return response.rule
            except grpc.RpcError:
                pass
            except Exception as e:
                print(f"⚠️ Error generating rule via Rust microservice: {e}. Falling back to Python.")

        if self.mock_llm:
            print(f"⚠️  Using MOCK LLM response for role: {role_name} (Stack: {stack})")
            return f"Always follow {stack} best practices."

        prompt = f"""
        You are a Data Analyst for an AI Swarm.
        Identify a pattern in these {count} failures for the role '{role_name}' working with stack '{stack}'.
        The failure note is: "{note}"

        Create a concise "Golden Rule" (HardConstraint) to prevent this in the future.
        The rule should be a short, imperative sentence (e.g., "Always verify hook order").
        Return ONLY the rule text.
        """
        optimized_prompt = self.optimize_prompt(prompt)
        return self.llm.completion(optimized_prompt).strip().strip('"')

    def validate_rule(self, rule_text: str, stack: str) -> bool:
        """Run sanity checks (dry-run) to validate the new rule."""
        if not self.sanity_suite:
            print("⚠️  No sanity suite loaded. Skipping validation.")
            return True

        tasks = self.sanity_suite.get('sanity_checks', {}).get(stack, [])
        if not tasks:
            print(f"⚠️  No sanity checks found for stack '{stack}'. Skipping validation.")
            return True

        print(f"🧪 Validating rule '{rule_text}' against {len(tasks)} sanity tasks for {stack}...")

        # Instantiate a temporary Orchestrator for dry-run
        # We need to ensure it doesn't pollute the main history, but Orchestrator currently writes to graph.
        # Ideally, we should use a "dry-run" flag in Orchestrator, but for now we accept the graph writes as "Test Execution"
        # Or we can just run it and let it be. The system is designed to learn from failures.

        # Use a separate orchestrator instance to avoid state pollution if any
        orch = OrchestratorAgent()

        all_passed = True
        for task_def in tasks:
            description = task_def['description']
            print(f"   Running sanity task: {description[:40]}...")

            # Pass the candidate rule as an extra rule
            result = orch.run(description, stack=stack, extra_rules=[rule_text])

            if result['final_status'] != 'success':
                print(f"❌ Sanity task failed! Rule '{rule_text}' caused regression.")
                all_passed = False
                break

            # Optionally check expected output content
            # This requires inspecting the artifacts or history, which is harder.
            # Assuming "success" status means it passed review.

        orch.close()

        if all_passed:
            print("✅ Rule validation passed.")
        return all_passed

    def run(self):
        # 0. Discovery Debug
        # self.debug_discovery()

        # New: Detect Schema Gaps
        self.detect_schema_gaps()

        print("🔍 Analyst scanning for failure patterns...")
        failures = self.find_unconsolidated_failures()
        print(f"Found {len(failures)} unconsolidated failures.")

        clusters = self.cluster_failures(failures)

        consolidated_count = 0
        new_rules = []

        for (role, note_text, stack), execIds in clusters.items():
            if len(execIds) >= self.threshold:
                print(f"⚠️  Found pattern: {len(execIds)} failures for {role} (Stack: {stack}) with note: {note_text[:50]}...")

                # 1. Generate Rule
                rule_text = self.generate_golden_rule(role, note_text, len(execIds), stack)
                print(f"📝 Proposed Golden Rule: {rule_text}")

                # 2. Validate Rule (Dry Run)
                if self.validate_rule(rule_text, stack):
                    print(f"✅ Rule validated. Persisting...")

                    # 3. Ingest Rule into Graph
                    # If stack is known, attach to Stack URI: http://swarm.os/stack/{stack}
                    # Else attach to Role

                    if stack and stack != "unknown":
                        subject = f"http://swarm.os/stack/{stack}"
                    else:
                        subject = role

                    rule_triples = [
                        {"subject": subject, "predicate": f"{NIST}HardConstraint", "object": f'"{rule_text}"'}
                    ]
                    self.ingest_triples(rule_triples)

                    # 4. Soft Delete (Mark as consolidated)
                    # <ExecId> swarm:isConsolidated "true"
                    consolidation_triples = []
                    for execId in execIds:
                        consolidation_triples.append({
                            "subject": execId,
                            "predicate": f"{SWARM}isConsolidated",
                            "object": '"true"'
                        })
                    self.ingest_triples(consolidation_triples)

                    # 5. Append to consolidated_wisdom.ttl
                    self.append_to_ttl(subject, rule_text)

                    # 6. Generate Security Restriction TTL File
                    self.save_security_restriction(subject, rule_text)

                    consolidated_count += len(execIds)
                    new_rules.append(rule_text)
                else:
                    print(f"⛔ Rule rejected due to validation failure.")

        print(f"🏁 Consolidation complete. Consolidated {consolidated_count} lessons. Generated {len(new_rules)} new rules.")

    def detect_schema_gaps(self):
        print("🔍 Analyst scanning for schema gaps...")
        # Query for errors related to ontology/schema
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX skos: <{SKOS}>
        PREFIX nist: <{NIST}>
        PREFIX rdf: <{RDF}>
        SELECT ?note ?execId
        WHERE {{
            ?execId rdf:type swarm:ExecutionRecord .
            ?execId nist:resultState "on_failure" .
            ?execId skos:historyNote ?note .
            FILTER (REGEX(?note, "schema", "i") || REGEX(?note, "ontology", "i") || REGEX(?note, "type", "i") || REGEX(?note, "class", "i"))
            FILTER NOT EXISTS {{ ?execId swarm:isConsolidated "true" }}
        }}
        """
        results = self.query_graph(query)

        if not results:
            return

        print(f"⚠️ Found {len(results)} potential schema issues.")

        # Aggregate notes
        notes = []
        execIds = []
        for r in results:
            note = r.get("?note") or r.get("note")
            if isinstance(note, dict): note = note.get('value', '')
            notes.append(note)
            execIds.append(r.get("?execId") or r.get("execId"))

        # Ask LLM to propose schema update
        prompt = f"""
        You are an Ontology Engineer.
        Analyze these error logs and identify missing concepts in the Swarm Ontology (namespace: {SWARM}).
        Logs:
        {json.dumps(notes[:10])}

        Propose a Turtle (.ttl) schema update to fix these gaps.
        Focus on adding missing Classes or Properties.
        Return ONLY the .ttl content. Start with @prefix.
        """
        try:
            optimized_prompt = self.optimize_prompt(prompt)
            ttl_content = self.llm.completion(optimized_prompt)

            # Security: Validate Content Size (Max 10KB)
            if len(ttl_content.encode('utf-8')) > 10 * 1024:
                print("❌ Schema update rejected: Content too large (>10KB)")
                return

            # Security: Basic Syntax Check
            if ("@prefix" not in ttl_content and "PREFIX" not in ttl_content) or "." not in ttl_content:
                print("❌ Schema update rejected: Invalid Turtle syntax (missing prefix or dot)")
                return

            filename = f"schema_update_{uuid.uuid4()}.ttl"
            # Canonical Path Resolution to prevent Traversal
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scenarios', 'suggested_schema'))
            os.makedirs(base_dir, exist_ok=True)
            path = os.path.join(base_dir, filename)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(ttl_content)
            print(f"📝 Proposed Schema Update saved to {path}")

            # Mark as consolidated
            triples = []
            for eid in execIds:
                triples.append({
                    "subject": eid if isinstance(eid, str) else eid.get('value'),
                    "predicate": f"{SWARM}isConsolidated",
                    "object": '"true"'
                })
            self.ingest_triples(triples)
        except Exception as e:
            print(f"❌ Schema update proposal failed: {e}")

    def append_to_ttl(self, subject, rule_text):
        path = os.path.join(os.path.dirname(__file__), '..', 'consolidated_wisdom.ttl')

        # Ensure subject is wrapped in <> if it's not already
        subj_str = subject
        if not subj_str.startswith('<'):
            subj_str = f"<{subj_str}>"

        with open(path, 'a') as f:
            f.write(f'{subj_str} <{NIST}HardConstraint> "{rule_text}" .\n')

    def save_security_restriction(self, subject, rule_text):
        """Generate a .ttl file for the security restriction."""
        restrictions_dir = os.path.join(os.path.dirname(__file__), '..', 'security_restrictions')
        if not os.path.exists(restrictions_dir):
            os.makedirs(restrictions_dir)

        file_uuid = uuid.uuid4()
        filepath = os.path.join(restrictions_dir, f"restriction_{file_uuid}.ttl")

        # Ensure subject is wrapped
        subj_str = subject
        if not subj_str.startswith('<'):
            subj_str = f"<{subj_str}>"

        content = f"""
@prefix nist: <{NIST}> .
@prefix swarm: <{SWARM}> .

{subj_str} nist:HardConstraint "{rule_text}" .
"""
        with open(filepath, 'w') as f:
            f.write(content.strip())
        print(f"🔒 Generated Security Restriction: {filepath}")

if __name__ == "__main__":
    analyst = AnalystAgent()
    analyst.run()
