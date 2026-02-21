#!/usr/bin/env python3
import os
import sys
import uuid
import grpc

# Add path to lib and agents
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

try:
    from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc

# Define Strict Namespaces
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
PROV = "http://www.w3.org/ns/prov#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS = "http://www.w3.org/2004/02/skos/core#"

class Simulator:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        self.namespace = "default"

    def ingest_triples(self, triples):
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace)
        self.stub.IngestTriples(request)

    def run(self):
        print("🧪 Simulating failures...")
        agent_uri = "http://swarm.os/agent/Coder"
        # Role URI derived from swarm_schema.yaml's ontology_role which becomes a URI by default in current engine unless quoted
        # Orchestrator sends "Frontend Developer" -> <http://synapse.os/Frontend Developer>
        # So we should use that or raw string "Frontend Developer" and let engine handle it.
        # But wait, we want to match.
        # Orchestrator code: `triples.append({"subject": subject, "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": ontology_role})`
        # `ontology_role` is "Frontend Developer".
        # Without quotes, the engine (patched) will treat "Frontend Developer" as <http://synapse.os/Frontend Developer>.
        # So here we should send "Frontend Developer" (no quotes) to match.
        role_object = "Frontend Developer"

        error_msg = '["SyntaxError: React hooks must be called in the same order in every component render."]'

        # Ensure Agent has a Role
        role_triples = [
             {"subject": agent_uri, "predicate": f"{RDF}type", "object": role_object}
        ]
        self.ingest_triples(role_triples)

        for i in range(6):
            exec_uuid = f"{SWARM}execution/{uuid.uuid4()}"
            print(f"   Injecting failure {i+1}: {exec_uuid}")

            triples = [
                 # Typed as ExecutionRecord
                 {"subject": exec_uuid, "predicate": f"{RDF}type", "object": f"{SWARM}ExecutionRecord"},
                 # Linked to Agent
                 {"subject": exec_uuid, "predicate": f"{PROV}wasAssociatedWith", "object": agent_uri},
                 # Result State (NIST) - QUOTED LITERAL
                 {"subject": exec_uuid, "predicate": f"{NIST}resultState", "object": '"on_failure"'},
                 # History Note (SKOS) - QUOTED LITERAL
                 {"subject": exec_uuid, "predicate": f"{SKOS}historyNote", "object": f'"{error_msg}"'},
                 # Inverse link for traversal
                 {"subject": agent_uri, "predicate": f"{SWARM}learnedFrom", "object": exec_uuid}
            ]
            self.ingest_triples(triples)

        print("✅ Simulation complete.")

if __name__ == "__main__":
    sim = Simulator()
    sim.run()
