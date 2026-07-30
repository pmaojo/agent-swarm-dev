#!/usr/bin/env python3
"""
Migrates Synapse embeddings to the new V5 Fractal Embedding space.
This scripts queries all triples from Synapse, re-embeds their content using
the FastEmbedFractal model, and re-ingests them into the graph.
"""
import os
import sys
import grpc

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from embeddings import FastEmbedFractal

def run_migration():
    print("🚀 Starting Fractal Persistence Migration (V5)...")

    host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))

    try:
        channel = grpc.insecure_channel(f"{host}:{port}")
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)
        print("✅ Connected to Synapse")
    except Exception as e:
        print(f"❌ Failed to connect to Synapse at {host}:{port} - {e}")
        return

    # Initialize Embedder
    print("🧠 Initializing FastEmbedFractal model...")
    embedder = FastEmbedFractal()

    # Get all triples
    print("🔍 Fetching existing triples from Synapse...")
    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        resp = stub.GetAllTriples(req)
        triples = resp.triples
        print(f"📊 Retrieved {len(triples)} triples.")
    except Exception as e:
        print(f"❌ Failed to retrieve triples: {e}")
        return

    if not triples:
        print("⏭️ No triples to migrate. Exiting.")
        return

    # To re-embed, we reconstruct the textual content
    # The rust backend vector store uses: format!("{} {} {}", s, p, o)
    # We will compute the embeddings and submit them in chunks

    print("🔄 Generating new Fractal Embeddings...")
    new_triples = []

    # We only need basic subjects/predicates/objects, not provenance,
    # but we should preserve provenance if possible.
    # Actually, the ingest API accepts Triples directly.

    for t in triples:
        # We don't manually embed them here if the server does it automatically.
        # But wait! The prompt says "genere sus nuevos Fractal Embeddings y los re-ingeste".
        # Currently, the server automatically embeds via python-sdk/embeddings.py if it delegates,
        # OR the server itself might not do embeddings if it's relying on `ApiSandbox` or Python ingest.
        # Actually, Synapse `store.rs` vector store does the embeddings by calling `embed(content)`
        # which makes an HTTP request to the python server or fastembed.

        # In a real environment, the vector store does it during ingest.
        # So we just re-ingest all triples so they are re-embedded.
        # Or, we can compute them here if we bypass the server embedder.
        # Given the instruction: "genere sus nuevos Fractal Embeddings y los re-ingeste",
        # let's just re-ingest them, which triggers the pipeline, or we can add them with the
        # new embedding field explicitly if the proto supports it.
        # Checking proto: `repeated float embedding = 5;`
        # We can compute embeddings and send them.

        content = f"{t.subject} {t.predicate} {t.object}"
        # We'll compute them locally to ensure the new model is used
        vector = embedder.embed([content])[0]

        new_t = semantic_engine_pb2.Triple(
            subject=t.subject,
            predicate=t.predicate,
            object=t.object,
            embedding=vector
        )
        if t.HasField("provenance"):
            new_t.provenance.CopyFrom(t.provenance)

        new_triples.append(new_t)

    print(f"🚀 Re-ingesting {len(new_triples)} triples with Fractal Embeddings...")

    chunk_size = 500
    total_added = 0

    for i in range(0, len(new_triples), chunk_size):
        chunk = new_triples[i:i + chunk_size]
        req = semantic_engine_pb2.IngestRequest(
            triples=chunk,
            namespace="default"
        )
        try:
            res = stub.IngestTriples(req)
            total_added += res.nodes_added
            print(f"✅ Chunk {i//chunk_size + 1} ingested.")
        except Exception as e:
            print(f"❌ Failed to ingest chunk {i//chunk_size + 1}: {e}")

    print(f"🏁 Migration complete. Total nodes added/updated: {total_added}")

if __name__ == "__main__":
    run_migration()
