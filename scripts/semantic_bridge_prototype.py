#!/usr/bin/env python3
"""
Semantic Bridge prototype.
This script demonstrates how to transform github/semantic JSON output
into Synapse triples for the Knowledge Graph.
"""
import json
import uuid
import sys
import os

# Swarm Ontology
SWARM = "http://swarm.os/ontology/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

def transform_semantic_json(file_path, semantic_json):
    """
    Transforms github/semantic symbols output into RDF triples.
    """
    triples = []
    file_uri = f"{SWARM}code/file/{file_path.replace('/', '_')}"
    
    # Add File Node
    triples.append({"subject": file_uri, "predicate": f"{RDF}type", "object": f"{SWARM}File"})
    triples.append({"subject": file_uri, "predicate": f"{SWARM}path", "object": f'"{file_path}"'})

    for symbol in semantic_json.get("files", [])[0].get("symbols", []):
        name = symbol.get("symbol")
        kind = symbol.get("kind")
        line = symbol.get("line")
        
        # Create unique URI for the symbol
        symbol_id = str(uuid.uuid4())[:8]
        symbol_uri = f"{file_uri}/{kind}/{name}_{symbol_id}"
        
        # Add Symbol Node
        triples.append({"subject": symbol_uri, "predicate": f"{RDF}type", "object": f"{SWARM}{kind.capitalize()}"})
        triples.append({"subject": symbol_uri, "predicate": f"{SWARM}name", "object": f'"{name}"'})
        triples.append({"subject": symbol_uri, "predicate": f"{SWARM}definedIn", "object": file_uri})
        triples.append({"subject": symbol_uri, "predicate": f"{SWARM}line", "object": f'"{line}"'})
        
        # Link File to Symbol
        triples.append({"subject": file_uri, "predicate": f"{SWARM}contains", "object": symbol_uri})
        
    return triples

def main():
    # Mocking semantic output for demonstration
    mock_semantic = {
        "files": [{
            "path": "sdk/python/lib/llm.py",
            "symbols": [
                {"symbol": "LLMService", "kind": "class", "line": 48},
                {"symbol": "completion", "kind": "method", "line": 282},
                {"symbol": "log_spend", "kind": "method", "line": 240}
            ]
        }]
    }
    
    print(f"🔍 Transforming symbols for: {mock_semantic['files'][0]['path']}")
    triples = transform_semantic_json(mock_semantic["files"][0]["path"], mock_semantic)
    
    print("\n🚀 Generated Triples for Synapse Ingestion:")
    for t in triples[:10]:
        print(f"  {t['subject']} --[{t['predicate']}]--> {t['object']}")
    print(f"  ... (+ {len(triples) - 10} more)")

if __name__ == "__main__":
    main()
