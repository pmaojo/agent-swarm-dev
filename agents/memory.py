#!/usr/bin/env python3
"""
Memory Agent - Synapse memory management
"""
import os
import sys
import json

# Add proto to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto'))

import grpc
import semantic_engine_pb2
import semantic_engine_pb2_grpc
from typing import Dict, Any, List, Optional

class MemoryAgent:
    def __init__(self, host: str = "localhost:50051", namespace: str = "default"):
        self.host = host
        self.namespace = namespace
        self.channel = None
        self.stub = None
        
    def connect(self):
        """Connect to Synapse"""
        self.channel = grpc.insecure_channel(self.host)
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        
    def add_triple(self, subject: str, predicate: str, object: str) -> bool:
        """Add a triple to the knowledge graph"""
        if not self.stub:
            self.connect()
            
        request = semantic_engine_pb2.IngestRequest(
            triples=[
                semantic_engine_pb2.Triple(
                    subject=subject,
                    predicate=predicate,
                    object=object
                )
            ],
            namespace=self.namespace
        )
        response = self.stub.IngestTriples(request)
        return response.edges_added > 0
    
    def query(self, sparql: str) -> List[Dict]:
        """Query the knowledge graph"""
        if not self.stub:
            self.connect()
            
        request = semantic_engine_pb2.SparqlRequest(
            query=sparql,
            namespace=self.namespace
        )
        response = self.stub.QuerySparql(request)
        return json.loads(response.results_json)
    
    def get_all(self, limit: int = 100) -> List[Dict]:
        """Get all triples"""
        if not self.stub:
            self.connect()
            
        request = semantic_engine_pb2.EmptyRequest()
        response = self.stub.GetAllTriples(request)
        return [
            {"s": t.subject, "p": t.predicate, "o": t.object}
            for t in response.triples[:limit]
        ]
    
    def run(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute memory action"""
        if not self.stub:
            self.connect()
            
        if action == "add":
            result = self.add_triple(
                kwargs["subject"],
                kwargs["predicate"],
                kwargs["object"]
            )
            return {"status": "success", "added": result}
        elif action == "query":
            results = self.query(kwargs["sparql"])
            return {"status": "success", "results": results}
        elif action == "get_all":
            results = self.get_all(kwargs.get("limit", 100))
            return {"status": "success", "triples": results}
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

if __name__ == "__main__":
    import sys
    agent = MemoryAgent()
    result = agent.run("get_all")
    print(json.dumps(result, indent=2))
