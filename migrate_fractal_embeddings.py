import os
import sys
import grpc
import json

# Add sdk paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "sdk/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "sdk/python/agents")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "sdk/python/lib")))

from synapse_proto import semantic_engine_pb2
from synapse_proto import semantic_engine_pb2_grpc
from embeddings import FastEmbedFractal

def migrate():
    port = os.environ.get("SYNAPSE_GRPC_PORT", "50051")
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    print("Fetching all triples...")
    # Get all stored triples
    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        res = stub.GetAllTriples(req)
        triples = res.triples
    except Exception as e:
        print(f"Failed to fetch triples: {e}")
        return

    print(f"Found {len(triples)} triples. Generating fractal embeddings...")

    embedder = FastEmbedFractal()

    # We will process them in batches
    batch_size = 100
    current_batch = []

    for i, t in enumerate(triples):
        # We'll embed the object (if it's a string literal or textual representation)
        # Or just embed the object URI/text
        text_to_embed = t.object if t.object else t.subject

        # FastEmbedFractal returns a list of vectors. We pass a list of 1 string.
        vectors = embedder.embed([text_to_embed])
        if vectors and len(vectors) > 0:
            embedding = vectors[0]

            # Create a new Triple with the embedding populated
            new_triple = semantic_engine_pb2.Triple(
                subject=t.subject,
                predicate=t.predicate,
                object=t.object,
                provenance=t.provenance,
                embedding=embedding
            )
            current_batch.append(new_triple)

        if len(current_batch) >= batch_size:
            print(f"Ingesting batch of {len(current_batch)} triples...")
            try:
                ingest_req = semantic_engine_pb2.IngestRequest(
                    triples=current_batch,
                    namespace="default"
                )
                stub.IngestTriples(ingest_req)
            except Exception as e:
                print(f"Failed to ingest batch: {e}")
            current_batch = []

    if len(current_batch) > 0:
        print(f"Ingesting final batch of {len(current_batch)} triples...")
        try:
            ingest_req = semantic_engine_pb2.IngestRequest(
                triples=current_batch,
                namespace="default"
            )
            stub.IngestTriples(ingest_req)
        except Exception as e:
            print(f"Failed to ingest final batch: {e}")

    print("Migration complete!")

if __name__ == "__main__":
    migrate()
