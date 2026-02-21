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
    from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    # Fallback if run from root
    from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from llm import LLMService

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

    def debug_discovery(self):
        """Debug function to dump raw triples to check IRI correctness."""
        print("🔍 DEBUG: Running discovery query (LIMIT 20)...")
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20"
        results = self.query_graph(query)
        for r in results:
            s = r.get("?s") or r.get("s")
            p = r.get("?p") or r.get("p")
            o = r.get("?o") or r.get("o")
            print(f"   <{s}> <{p}> <{o}>")

    def find_unconsolidated_failures(self):
        # Strict Namespace Query with Literal Matching

        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX nist: <{NIST}>
        PREFIX prov: <{PROV}>
        PREFIX rdf: <{RDF}>
        PREFIX skos: <{SKOS}>

        SELECT ?execId ?agent ?role ?note
        WHERE {{
            ?execId rdf:type swarm:ExecutionRecord .
            ?execId nist:resultState "on_failure" .
            ?execId prov:wasAssociatedWith ?agent .
            ?agent rdf:type ?role .
            ?execId skos:historyNote ?note .

            FILTER NOT EXISTS {{ ?execId swarm:isConsolidated "true" }}
        }}
        """
        return self.query_graph(query)

    def cluster_failures(self, failures):
        clusters = defaultdict(list)
        for f in failures:
            role = f.get('role') or f.get('?role')
            note = f.get('note') or f.get('?note')
            execId = f.get('execId') or f.get('?execId')

            # Note is a literal, check if it's a JSON string
            if isinstance(note, dict):
                note = note.get('value', '')

            try:
                # Remove surrounding quotes from JSON string if double-encoded
                if note.startswith('"') and note.endswith('"') and len(note) > 1:
                     note = note[1:-1]

                if note.startswith('[') and note.endswith(']'):
                   parsed = json.loads(note)
                   if isinstance(parsed, list) and parsed:
                       note = parsed[0]
            except:
                pass

            # Simple clustering: exact match on (role, note)
            key = (role, note)
            clusters[key].append(execId)
        return clusters

    def generate_golden_rule(self, role, note, count):
        # Clean Role for Prompt (it's a URI)
        role_name = role.split('/')[-1]

        if self.mock_llm:
            print(f"⚠️  Using MOCK LLM response for role: {role_name}")
            return "Always verify React hooks order in components."

        prompt = f"""
        You are a Data Analyst for an AI Swarm.
        Identify a pattern in these {count} failures for the role '{role_name}'.
        The failure note is: "{note}"

        Create a concise "Golden Rule" (HardConstraint) to prevent this in the future.
        The rule should be a short, imperative sentence (e.g., "Always verify hook order").
        Return ONLY the rule text.
        """
        return self.llm.completion(prompt).strip().strip('"')

    def run(self):
        # 0. Discovery Debug
        # self.debug_discovery()

        print("🔍 Analyst scanning for failure patterns...")
        failures = self.find_unconsolidated_failures()
        print(f"Found {len(failures)} unconsolidated failures.")

        clusters = self.cluster_failures(failures)

        consolidated_count = 0
        new_rules = []

        for (role, note_text), execIds in clusters.items():
            if len(execIds) >= self.threshold:
                print(f"⚠️  Found pattern: {len(execIds)} failures for {role} with note: {note_text[:50]}...")

                # 1. Generate Rule
                rule_text = self.generate_golden_rule(role, note_text, len(execIds))
                print(f"✅ Generated Golden Rule: {rule_text}")

                # 2. Ingest Rule into Graph
                # <Role> nist:HardConstraint "Rule"
                # Wrapping rule_text in escaped quotes to encourage literal treatment
                # Role is already a URI string (e.g. http://synapse.os/Frontend Developer) from SPARQL result
                rule_triples = [
                    {"subject": role, "predicate": f"{NIST}HardConstraint", "object": f'"{rule_text}"'}
                ]
                self.ingest_triples(rule_triples)

                # 3. Soft Delete (Mark as consolidated)
                # <ExecId> swarm:isConsolidated "true"
                consolidation_triples = []
                for execId in execIds:
                    consolidation_triples.append({
                        "subject": execId,
                        "predicate": f"{SWARM}isConsolidated",
                        "object": '"true"'
                    })
                self.ingest_triples(consolidation_triples)

                # 4. Append to consolidated_wisdom.ttl
                self.append_to_ttl(role, rule_text)

                consolidated_count += len(execIds)
                new_rules.append(rule_text)

        print(f"🏁 Consolidation complete. Consolidated {consolidated_count} lessons. Generated {len(new_rules)} new rules.")

    def append_to_ttl(self, role, rule_text):
        path = os.path.join(os.path.dirname(__file__), '..', 'consolidated_wisdom.ttl')

        # Ensure role is wrapped in <> if it's not already
        role_str = role
        if not role_str.startswith('<'):
            role_str = f"<{role_str}>"

        with open(path, 'a') as f:
            f.write(f'{role_str} <{NIST}HardConstraint> "{rule_text}" .\n')

if __name__ == "__main__":
    analyst = AnalystAgent()
    analyst.run()
