#!/usr/bin/env python3
"""
Migrates Synapse nodes to V5 Fractal Embeddings using FractalProjectionHead.
"""
import os
import sys
import grpc
import json
from dotenv import load_dotenv

# Add paths
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents", "synapse_proto"))
try:
    import semantic_engine_pb2
    import semantic_engine_pb2_grpc
except ImportError:
    pass

from embeddings import FastEmbedFractal

def migrate():
    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))
    host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))

    print(f"Connecting to Synapse at {host}:{port}")
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    # Get all triples
    print("Fetching all triples...")
    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        response = stub.GetAllTriples(req)
        triples = response.triples
        print(f"Found {len(triples)} triples.")
    except Exception as e:
        print(f"Failed to fetch triples: {e}")
        return

    if not triples:
        print("No triples to migrate.")
        return

    # Initialize embedder
    print("Initializing FastEmbedFractal...")
    embedder = FastEmbedFractal()

    # We need to re-embed the object text or the subject string representation
    # Triples often have literals as objects. We'll find literals and embed them.
    # We will re-ingest all triples to update their embeddings if we change them.
    # Actually, the simplest way is to collect texts, embed, and re-ingest.

    updated_triples = []
    texts_to_embed = []

    for t in triples:
        # A simple heuristic: embed the object if it looks like a literal or name
        # We will embed the subject's local name or the object string
        content = f"{t.subject} {t.predicate} {t.object}"
        texts_to_embed.append(content)

    print(f"Generating fractal embeddings for {len(texts_to_embed)} items...")

    # Process in batches
    batch_size = 32
    all_embeddings = []
    for i in range(0, len(texts_to_embed), batch_size):
        batch = texts_to_embed[i:i+batch_size]
        emb = embedder.embed(batch)
        all_embeddings.extend(emb)
        print(f"Embedded {len(all_embeddings)}/{len(texts_to_embed)}")

    print("Reconstructing triples with fractal embeddings...")
    for i, t in enumerate(triples):
        new_triple = semantic_engine_pb2.Triple(
            subject=t.subject,
            predicate=t.predicate,
            object=t.object,
            provenance=t.provenance,
            embedding=all_embeddings[i]
        )
        updated_triples.append(new_triple)

    print("Re-ingesting updated triples...")
    try:
        ingest_req = semantic_engine_pb2.IngestRequest(
            triples=updated_triples,
            namespace="default"
        )
        ingest_res = stub.IngestTriples(ingest_req)
        print(f"Successfully migrated embeddings. Added {ingest_res.nodes_added} nodes, {ingest_res.edges_added} edges.")
    except Exception as e:
        print(f"Failed to ingest triples: {e}")

if __name__ == "__main__":
    migrate()
