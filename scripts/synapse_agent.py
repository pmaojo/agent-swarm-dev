#!/usr/bin/env python3
"""
Synapse Agent - MCP Tool for Agent Swarm Development
Integra el SDK de synapse con el sistema de desarrollo de agentes.
"""

from synapse import get_client
import json
import sys

def ingestKnowledge(data: dict) -> str:
    """Ingesta conocimiento al grafo"""
    client = get_client()
    triples = data.get("triples", [])
    namespace = data.get("namespace", "default")
    
    client.ingest_triples(triples, namespace=namespace)
    return f"✅ Ingestados {len(triples)} triples en namespace {namespace}"

def queryGraph(query: str, namespace: str = "default") -> str:
    """Consulta el grafo con SPARQL"""
    client = get_client()
    results = client.query_sparql(query, namespace=namespace)
    return json.dumps(results, indent=2)

def addObservation(subject: str, predicate: str, obj: str, namespace: str = "default") -> str:
    """Añade una observación al grafo"""
    client = get_client()
    client.ingest_triples([
        {"subject": subject, "predicate": predicate, "object": obj}
    ], namespace=namespace)
    return f"✅ Añadido: {subject} {predicate} {obj}"

def main():
    if len(sys.argv) < 3:
        print("Usage: synapse_agent.py <action> <json_data>")
        sys.exit(1)
    
    action = sys.argv[1]
    data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    
    namespace = data.get("namespace", "default")
    
    if action == "ingest":
        print(ingestKnowledge(data))
    elif action == "query":
        print(queryGraph(data.get("query", ""), namespace))
    elif action == "observe":
        print(addObservation(
            data.get("subject", ""),
            data.get("predicate", ""),
            data.get("object", ""),
            namespace
        ))
    else:
        print(f"❌ Acción desconocida: {action}")

if __name__ == "__main__":
    main()
