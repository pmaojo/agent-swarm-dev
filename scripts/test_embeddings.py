#!/usr/bin/env python3
import sys
import json
from synapse import get_client

def test_embeddings_and_search():
    client = get_client()

    # 1. Ingest some test documents
    print("\n📥 Ingesting test documents...")
    triples = [
        {"subject": "doc:1", "predicate": "content", "object": "The quick brown fox jumps over the lazy dog."},
        {"subject": "doc:2", "predicate": "content", "object": "Machine learning models rely on vast amounts of data."},
        {"subject": "doc:3", "predicate": "content", "object": "Product Managers define the roadmap."}
    ]

    try:
        client.ingest_triples(triples, namespace="test_vectors")
        print("✅ Triples ingested.")
    except Exception as e:
        print(f"❌ Ingest failed: {e}")

    # 2. Test Vector Search via 'hybrid_search'
    print("\n🔍 Testing Vector Search (Hybrid)...")
    query_text = "Who manages the roadmap?"
    try:
        # Assuming hybrid_search signature based on dir output
        results = client.hybrid_search(query_text, namespace="test_vectors", limit=2)
        print(f"Query: '{query_text}'")
        print(f"Results: {json.dumps(results, indent=2)}")
    except Exception as e:
        print(f"❌ Hybrid search failed: {e}")

    # 3. Test Knowledge Retrieval (SPARQL) via 'sparql_query'
    print("\n🧠 Testing Knowledge Retrieval (SPARQL)...")
    sparql = """
    PREFIX org: <http://example.org/org#>
    SELECT ?s ?p ?o
    WHERE {
        ?s <pertenece_a_area> ?area .
        FILTER(CONTAINS(STR(?area), "Ingeniería"))
    }
    LIMIT 5
    """
    try:
        # Note: Depending on how triples were ingested, predicates might be IRIs or literals.
        # The ingestion script treated them as raw strings in JSON, which Synapse likely handles as relative IRIs or Literals.
        # Let's try a simpler query first.
        simple_query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5"

        results = client.sparql_query(simple_query, namespace="org")
        print(f"SPARQL Results (Sample):\n{json.dumps(results, indent=2)}")

        # Now try filtering
        filtered_results = client.sparql_query(sparql, namespace="org")
        print(f"SPARQL Filtered Results:\n{json.dumps(filtered_results, indent=2)}")

    except Exception as e:
        print(f"❌ SPARQL query failed: {e}")

if __name__ == "__main__":
    test_embeddings_and_search()
