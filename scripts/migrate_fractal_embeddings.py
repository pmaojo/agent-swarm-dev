#!/usr/bin/env python3
"""
Fractal Embedding Migration Script
Fetches all nodes, generates Fractal Embeddings using bge-small + FractalProjectionHead,
and re-ingests them into Synapse to enable V5 Fractal Search.
"""
import os
import sys
import grpc
import json

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

from embeddings import FastEmbedFractal
from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc

def run_migration():
    print("🚀 Initializing Fractal Embedding Migration...")

    grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50052"))
    namespace = "default"

    try:
        channel = grpc.insecure_channel(
            f"{grpc_host}:{grpc_port}",
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024)
            ]
        )
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)
        print("✅ Connected to Synapse")
    except grpc.FutureTimeoutError:
        print("⚠️ Synapse not reachable. Exiting.")
        return
    except Exception as e:
        print(f"❌ Failed to connect to Synapse: {e}")
        return

    try:
        print("⏳ Loading Fractal Embedder (~2.5M params MLP)...")
        embedder = FastEmbedFractal()
        print("✅ Embedder ready")
    except Exception as e:
        print(f"❌ Failed to load embedder: {e}")
        return

    print("📥 Fetching all triples from Synapse...")
    try:
        req = semantic_engine_pb2.EmptyRequest(namespace=namespace)
        res = stub.GetAllTriples(req)
        triples = res.triples
        print(f"✅ Found {len(triples)} triples in namespace '{namespace}'")
    except Exception as e:
        print(f"❌ Failed to fetch triples: {e}")
        return

    if not triples:
        print("ℹ️ No triples found to migrate.")
        return

    print("🧬 Generating Fractal Embeddings...")

    # Generate texts for triples to embed
    texts_to_embed = []
    for t in triples:
        text = f"{t.subject} {t.predicate} {t.object}"
        texts_to_embed.append(text)

    try:
        # We process in batches to avoid OOM or huge memory spikes
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts_to_embed), batch_size):
            batch_texts = texts_to_embed[i:i+batch_size]
            batch_embeddings = embedder.embed(batch_texts)
            all_embeddings.extend(batch_embeddings)
            print(f"   Processed {len(all_embeddings)}/{len(texts_to_embed)}...")
    except Exception as e:
        print(f"❌ Failed to generate embeddings: {e}")
        return

    print("📤 Re-ingesting triples with Fractal Embeddings...")
    new_triples = []
    for i, t in enumerate(triples):
        new_t = semantic_engine_pb2.Triple(
            subject=t.subject,
            predicate=t.predicate,
            object=t.object,
            embedding=all_embeddings[i]
        )
        if t.provenance:
            new_t.provenance.CopyFrom(t.provenance)
        new_triples.append(new_t)

    # Ingest in batches to avoid gRPC size limits
    ingest_batch_size = 500
    total_added = 0

    for i in range(0, len(new_triples), ingest_batch_size):
        batch = new_triples[i:i+ingest_batch_size]
        try:
            req = semantic_engine_pb2.IngestRequest(
                triples=batch,
                namespace=namespace
            )
            res = stub.IngestTriples(req)
            total_added += res.nodes_added # Note: this might be nodes or triples
            print(f"   Ingested batch {i//ingest_batch_size + 1}...")
        except Exception as e:
            print(f"❌ Failed to ingest batch: {e}")

    print("🎉 Fractal Migration Complete!")

if __name__ == "__main__":
    run_migration()
