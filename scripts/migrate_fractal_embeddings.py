import os
import json
import asyncio
import sys
import grpc

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

from embeddings import FastEmbedFractal
try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc

def migrate_fractal_embeddings():
    grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
    namespace = "default"

    print(f"Connecting to Synapse Engine at {grpc_host}:{grpc_port}")
    channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}")
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    # Initialize FastEmbedFractal
    print("Initializing FastEmbedFractal...")
    embedder = FastEmbedFractal()

    # Query existing nodes in Synapse
    print("Querying existing nodes...")
    query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
    req = semantic_engine_pb2.SparqlRequest(query=query, namespace=namespace)

    try:
        res = stub.QuerySparql(req)
        results = json.loads(res.results_json)
    except Exception as e:
        print(f"Error querying Synapse: {e}")
        return

    if not results:
        print("No triples found in the namespace.")
        return

    print(f"Found {len(results)} triples. Starting migration...")

    # For each node/triple, we generate its new Fractal Embedding and re-ingest
    # In reality, embeddings might be bound to the subject or object.
    # We will iterate through triples, compute embeddings for their string representation,
    # and re-ingest them as new Triples with the `embedding` field populated.

    batch_size = 100
    triples_to_ingest = []

    # Increase max payload size for channel if possible. grpc.insecure_channel doesn't allow changing it after creation.
    # But since we use batching, it should be fine. We can set it in channel options if needed.

    channel_options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024)
    ]
    channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}", options=channel_options)
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    for i in range(0, len(results), batch_size):
        batch = results[i:i+batch_size]
        batch_triples = []
        batch_texts = []

        for r in batch:
            # Depending on how the SPARQL response is formatted
            # For oxigraph we often get { "?s": "val", "?p": "val", "?o": "val" }
            # or with prefixes.
            s = r.get("s", r.get("?s", ""))
            p = r.get("p", r.get("?p", ""))
            o = r.get("o", r.get("?o", ""))

            # Unescape or clean if necessary
            if isinstance(s, dict): s = s.get("value", str(s))
            if isinstance(p, dict): p = p.get("value", str(p))
            if isinstance(o, dict): o = o.get("value", str(o))

            text_repr = f"{s} {p} {o}"
            batch_texts.append(text_repr)
            batch_triples.append((s, p, o))

        # Compute embeddings for the batch
        embeddings = embedder.embed(batch_texts)

        # Prepare ingestion payload
        pb_triples = []
        for j, (s, p, o) in enumerate(batch_triples):
            t = semantic_engine_pb2.Triple(
                subject=s,
                predicate=p,
                object=o,
                embedding=embeddings[j] if j < len(embeddings) else []
            )
            pb_triples.append(t)

        ingest_req = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=namespace)
        try:
            stub.IngestTriples(ingest_req)
            print(f"Re-ingested batch {i // batch_size + 1}")
        except Exception as e:
            print(f"Error ingesting batch: {e}")

    print("Migration complete.")

if __name__ == "__main__":
    migrate_fractal_embeddings()
