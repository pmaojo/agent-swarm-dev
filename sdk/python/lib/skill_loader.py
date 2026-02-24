#!/usr/bin/env python3
"""
Skill Loader - Ingests Skills into Synapse Knowledge Graph.
"""
import os
import json
import grpc
import sys

# Synapse Imports
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)
try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None

SWARM = "http://swarm.os/ontology/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

def ingest_skills():
    if not semantic_engine_pb2_grpc:
        print("❌ Synapse not available.")
        return

    grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))

    try:
        channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}")
        stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

        # Load JSON
        data_path = os.path.join(SDK_PYTHON_PATH, "data", "skills.json")
        with open(data_path, "r") as f:
            skills = json.load(f)

        triples = []
        for skill in skills:
            s_uri = f"{SWARM}{skill['id']}"
            triples.append({"subject": s_uri, "predicate": f"{RDF}type", "object": f"{SWARM}Skill"})
            triples.append({"subject": s_uri, "predicate": f"{SWARM}name", "object": f'"{skill["name"]}"'})
            triples.append({"subject": s_uri, "predicate": f"{SWARM}description", "object": f'"{skill["description"]}"'})
            triples.append({"subject": s_uri, "predicate": f"{SWARM}level", "object": f'"{skill["level"]}"'})

            for pre in skill.get("prerequisites", []):
                p_uri = f"{SWARM}{pre}"
                triples.append({"subject": s_uri, "predicate": f"{SWARM}requiresSkill", "object": p_uri})

        # Assign default skills to Coder (Bootstrap)
        # TODO: Move this to a proper onboarding flow
        coder_uri = f"{SWARM}agent/Coder"
        for skill in skills:
             # Auto-unlock level 1 skills for now
             if skill.get("level", 1) == 1:
                 s_uri = f"{SWARM}{skill['id']}"
                 triples.append({"subject": coder_uri, "predicate": f"{SWARM}hasSkill", "object": s_uri})

        # Ingest
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace="default"))
        print(f"✅ Ingested {len(skills)} skills into Synapse.")

    except Exception as e:
        print(f"❌ Failed to ingest skills: {e}")

if __name__ == "__main__":
    ingest_skills()
