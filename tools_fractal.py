import os
import json
import uuid
import grpc
from sdk.python.agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from sdk.python.lib.embeddings import FastEmbedFractal

class FractalMigrator:
    def __init__(self):
        self.channel = grpc.insecure_channel("localhost:50052")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        self.embedder = FastEmbedFractal()
        self.namespace = "default"

    def fetch_all_nodes(self):
        query = """
        SELECT ?s ?p ?o WHERE {
            ?s ?p ?o .
            FILTER (isLiteral(?o) || isURI(?o))
        }
        """
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
        try:
            res = self.stub.QuerySparql(request)
            return json.loads(res.results_json)
        except Exception as e:
            print(f"Error fetching: {e}")
            return []

    def migrate(self):
        triples = self.fetch_all_nodes()
        print(f"Found {len(triples)} triples")

        if not triples:
            return

        batch_size = 50
        batches = []
        current_batch = []

        for t in triples:
            s = t.get("?s") or t.get("s")
            p = t.get("?p") or t.get("p")
            o = t.get("?o") or t.get("o")

            # Simple content extraction
            content = f"{s} {p} {o}"
            current_batch.append((s, p, o, content))
            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []
        if current_batch:
            batches.append(current_batch)

        total_migrated = 0
        for batch in batches:
            texts = [b[3] for b in batch]
            embeddings = self.embedder.embed(texts)

            pb_triples = []
            for (s, p, o, _), emb in zip(batch, embeddings):
                pb_triples.append(semantic_engine_pb2.Triple(
                    subject=s,
                    predicate=p,
                    object=o,
                    embedding=emb
                ))

            req = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace)
            self.stub.IngestTriples(req)
            total_migrated += len(batch)
            print(f"Migrated {total_migrated}/{len(triples)}")

        print("Migration complete.")

if __name__ == "__main__":
    m = FractalMigrator()
    print("Testing connection...")
    m.migrate()
