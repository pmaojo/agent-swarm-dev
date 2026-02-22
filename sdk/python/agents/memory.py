#!/usr/bin/env python3
"""
Memory Agent - Synapse memory management
"""
import os
import sys
import json
import grpc

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from typing import Any, Dict, List, Optional


class MemoryAgentError(RuntimeError):
    """Raised when the MemoryAgent cannot execute an operation."""

class MemoryAgent:
    def __init__(self, host: str = "localhost:50051", namespace: str = "default"):
        self.host = host
        self.namespace = self._validate_namespace(namespace)
        self.channel: Optional[grpc.Channel] = None
        self.stub: Optional[semantic_engine_pb2_grpc.SemanticEngineStub] = None

    def _validate_namespace(self, namespace: str) -> str:
        normalized = namespace.strip()
        if not normalized:
            raise ValueError("[MemoryAgent] Invalid namespace: namespace cannot be empty")
        return normalized

    def connect(self) -> None:
        """Connect to Synapse"""
        try:
            self.channel = grpc.insecure_channel(self.host)
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except grpc.RpcError as exc:
            self.channel = None
            self.stub = None
            raise MemoryAgentError(
                f"[MemoryAgent] Connection failed host={self.host} namespace={self.namespace}: {exc}"
            ) from exc
        except Exception as exc:
            self.channel = None
            self.stub = None
            raise MemoryAgentError(
                f"[MemoryAgent] Unexpected connection error host={self.host} namespace={self.namespace}: {exc}"
            ) from exc

    def _ensure_stub(self) -> semantic_engine_pb2_grpc.SemanticEngineStub:
        if self.stub is None:
            self.connect()

        if self.stub is None:
            raise MemoryAgentError(
                f"[MemoryAgent] Connection unavailable host={self.host} namespace={self.namespace}"
            )

        return self.stub

    def add_triple(self, subject: str, predicate: str, object: str) -> bool:
        """Add a triple to the knowledge graph"""
        stub = self._ensure_stub()

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
        try:
            response = stub.IngestTriples(request)
            return response.edges_added > 0
        except grpc.RpcError as exc:
            raise MemoryAgentError(
                f"[MemoryAgent] add_triple failed host={self.host} namespace={self.namespace}: {exc}"
            ) from exc
    
    def query(self, sparql: str) -> List[Dict]:
        """Query the knowledge graph"""
        stub = self._ensure_stub()

        request = semantic_engine_pb2.SparqlRequest(
            query=sparql,
            namespace=self.namespace
        )
        try:
            response = stub.QuerySparql(request)
            return json.loads(response.results_json)
        except (grpc.RpcError, json.JSONDecodeError) as exc:
            raise MemoryAgentError(
                f"[MemoryAgent] query failed host={self.host} namespace={self.namespace}: {exc}"
            ) from exc
    
    def get_all(self, limit: int = 100) -> List[Dict]:
        """Get all triples"""
        stub = self._ensure_stub()

        request = semantic_engine_pb2.EmptyRequest()
        try:
            response = stub.GetAllTriples(request)
            return [
                {"s": t.subject, "p": t.predicate, "o": t.object}
                for t in response.triples[:limit]
            ]
        except grpc.RpcError as exc:
            raise MemoryAgentError(
                f"[MemoryAgent] get_all failed host={self.host} namespace={self.namespace}: {exc}"
            ) from exc
    
    def run(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute memory action"""
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
