#!/usr/bin/env python3
"""
Analyst Agent - Consolidates failure patterns into Golden Rules.
"""
import os
import sys
import json
import grpc
import yaml
import time
from collections import defaultdict
from typing import List, Dict, Any, Optional

# Add path to lib and agents
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from llm import LLMService
from orchestrator import OrchestratorAgent

# Define Strict Namespaces
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
PROV = "http://www.w3.org/ns/prov#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS = "http://www.w3.org/2004/02/skos/core#"

class AnalystAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.namespace = "default"
        self.llm = LLMService()
        self.channel = None
        self.stub = None

        self.connect()
        self.config = self.load_config()
        self.threshold = self.config.get('memory_settings', {}).get('consolidation_threshold', 5)
        self.mock_llm = os.getenv("MOCK_LLM", "true").lower() == "true"
        self.sanity_suite = self.load_sanity_suite()

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

    def optimize_prompt(self, prompt_text: str) -> str:
        """
        Removes stop words and redundant whitespace to optimize token usage.
        """
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "for", "on", "with", "at", "by", "from", "up", "about", "into", "over", "after"}
        words = prompt_text.split()
        optimized_words = [word for word in words if word.lower() not in stop_words]
        return " ".join(optimized_words)

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

    def generate_golden_rule(self, role, note, count, stack):
        # Clean Role for Prompt (it's a URI)
        role_name = role.split('/')[-1]

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

        # Optimize prompt before sending
        optimized_prompt = self.optimize_prompt(prompt)
        print(f"📉 Optimized prompt length: {len(prompt)} -> {len(optimized_prompt)}")

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

                    consolidated_count += len(execIds)
                    new_rules.append(rule_text)
                else:
                    print(f"⛔ Rule rejected due to validation failure.")

        print(f"🏁 Consolidation complete. Consolidated {consolidated_count} lessons. Generated {len(new_rules)} new rules.")

    def append_to_ttl(self, subject, rule_text):
        path = os.path.join(os.path.dirname(__file__), '..', 'consolidated_wisdom.ttl')

        # Ensure subject is wrapped in <> if it's not already
        subj_str = subject
        if not subj_str.startswith('<'):
            subj_str = f"<{subj_str}>"

        with open(path, 'a') as f:
            f.write(f'{subj_str} <{NIST}HardConstraint> "{rule_text}" .\n')

if __name__ == "__main__":
    analyst = AnalystAgent()
    analyst.run()
