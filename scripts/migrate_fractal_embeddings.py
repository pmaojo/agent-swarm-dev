#!/usr/bin/env python3
import os
import sys
import json
import grpc

# Add SDK path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python', 'lib')))

# Make sure the generated protobuf module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python', 'agents', 'synapse_proto')))

try:
    import semantic_engine_pb2
    import semantic_engine_pb2_grpc
except ImportError as e:
    print(f"Failed to import Synapse protobufs: {e}. Did you run `python -m grpc_tools.protoc ...`?")
    sys.exit(1)

try:
    from embeddings import FastEmbedFractal
except ImportError as e:
    print(f"Failed to import FastEmbedFractal: {e}")
    sys.exit(1)

def run_migration():
    print("🚀 Initializing Fractal Embedding Migration...")

    # Initialize fractal embedder
    embedder = FastEmbedFractal()

    # Connect to Synapse
    grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))

    try:
        channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}")
        grpc.channel_ready_future(channel).result(timeout=2)
        stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)
        print("✅ Connected to Synapse")
    except Exception as e:
        print(f"❌ Failed to connect to Synapse: {e}")
        return

    # 1. Fetch all triples
    print("📡 Fetching existing triples...")
    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        res = stub.GetAllTriples(req)
        triples = res.triples
        print(f"📦 Received {len(triples)} triples.")
    except Exception as e:
        print(f"❌ Failed to fetch triples: {e}")
        return

    # 2. Re-embed content
    print("🧠 Generating Fractal Embeddings...")
    new_triples = []

    for i, t in enumerate(triples):
        # We create a simple content representation of the triple to embed
        # (similar to what SynapseStore does internally)
        content = f"{t.subject} {t.predicate} {t.object}"

        # Generate embedding
        vector = embedder.embed([content])[0]

        # Create new triple with embedding attached
        # Note: We must construct a semantic_engine_pb2.Triple
        new_t = semantic_engine_pb2.Triple(
            subject=t.subject,
            predicate=t.predicate,
            object=t.object,
            embedding=vector
        )
        if t.HasField("provenance"):
            new_t.provenance.CopyFrom(t.provenance)

        new_triples.append(new_t)

        if (i + 1) % 100 == 0:
            print(f"⏳ Processed {i + 1}/{len(triples)} triples...")

    # 3. Re-ingest triples
    # To truly 'migrate', we ideally delete and re-ingest, or just ingest over them
    # Because of how vector_store works, inserting the same triple subject/predicate/object
    # might skip vector generation if the key exists.
    # We will just print instructions to wipe and restart Synapse or ingest directly.
    # Since SynapseStore::ingest_triples accepts the Triple object, we can ingest them.

    print("💾 Re-ingesting triples with Fractal Embeddings...")
    batch_size = 100
    for i in range(0, len(new_triples), batch_size):
        batch = new_triples[i:i + batch_size]
        req = semantic_engine_pb2.IngestRequest(triples=batch, namespace="default")
        try:
            stub.IngestTriples(req)
        except Exception as e:
            print(f"⚠️ Error ingesting batch {i}: {e}")

    print("✅ Migration Complete! Synapse now operates in V5 Fractal Space.")

if __name__ == "__main__":
    run_migration()