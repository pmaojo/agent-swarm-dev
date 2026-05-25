"""
LocalSynapseStub — drop-in replacement for SemanticEngineStub that uses
rdflib (already in requirements.txt) instead of a gRPC server.

Persists each namespace to a .nq (N-Quads) file under SYNAPSE_DATA_DIR
(default: .synapse_data/).  All three operations used by the swarm agents
are supported:  IngestTriples, QuerySparql, HybridSearch.
"""

import json
import os
import logging
from dataclasses import dataclass, field
from typing import List

import rdflib
from rdflib import ConjunctiveGraph, URIRef, Literal

logger = logging.getLogger("LocalSynapse")

_DATA_DIR = os.getenv("SYNAPSE_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", ".synapse_data"))


# ── Response objects matching the protobuf message shapes ──────────────────

@dataclass
class IngestResponse:
    nodes_added: int = 0
    edges_added: int = 0


@dataclass
class SparqlResponse:
    results_json: str = "[]"


@dataclass
class SearchResult:
    uri: str = ""
    content: str = ""
    score: float = 0.0
    node_id: int = 0


@dataclass
class SearchResponse:
    results: List[SearchResult] = field(default_factory=list)


# ── Core stub ──────────────────────────────────────────────────────────────

class LocalSynapseStub:
    """
    Implements the same three methods that all SDK agents call:
        .IngestTriples(request)  → IngestResponse
        .QuerySparql(request)    → SparqlResponse
        .HybridSearch(request)   → SearchResponse
    """

    def __init__(self, data_dir: str = _DATA_DIR):
        self._data_dir = os.path.abspath(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._graphs: dict[str, ConjunctiveGraph] = {}
        logger.info("LocalSynapseStub initialised (data: %s)", self._data_dir)

    # ── internals ──────────────────────────────────────────────────────────

    def _graph(self, namespace: str) -> ConjunctiveGraph:
        if namespace not in self._graphs:
            g = ConjunctiveGraph()
            path = self._nq_path(namespace)
            if os.path.exists(path):
                try:
                    g.parse(path, format="nquads")
                except Exception as e:
                    logger.warning("Could not load %s: %s", path, e)
            self._graphs[namespace] = g
        return self._graphs[namespace]

    def _nq_path(self, namespace: str) -> str:
        safe = namespace.replace("/", "_").replace(":", "_")
        return os.path.join(self._data_dir, f"{safe}.nq")

    def _save(self, namespace: str) -> None:
        g = self._graphs.get(namespace)
        if g is None:
            return
        try:
            g.serialize(destination=self._nq_path(namespace), format="nquads")
        except Exception as e:
            logger.warning("Could not persist graph '%s': %s", namespace, e)

    @staticmethod
    def _term(s: str):
        """Parse a raw string into an rdflib term."""
        s = s.strip()
        if s.startswith("<") and s.endswith(">"):
            return URIRef(s[1:-1])
        if s.startswith("http://") or s.startswith("https://") or s.startswith("urn:"):
            return URIRef(s)
        if s.startswith('"') and s.endswith('"'):
            return Literal(s[1:-1])
        return Literal(s)

    # ── public API ─────────────────────────────────────────────────────────

    def IngestTriples(self, request):
        ns = request.namespace or "default"
        g = self._graph(ns)
        added = 0
        for t in request.triples:
            try:
                subj = self._term(t.subject)
                if isinstance(subj, Literal):
                    subj = URIRef(f"urn:swarm:{str(subj)}")
                pred = self._term(t.predicate)
                obj  = self._term(t.object)
                g.add((subj, pred, obj))
                added += 1
            except Exception as e:
                logger.debug("Skipping malformed triple: %s", e)
        self._save(ns)
        return IngestResponse(nodes_added=added, edges_added=added)

    def QuerySparql(self, request):
        ns = request.namespace or "default"
        g = self._graph(ns)
        try:
            results = g.query(request.query)
            if results.type == "SELECT":
                rows = []
                for row in results:
                    row_dict = {}
                    for var in results.vars:
                        val = row.get(var)
                        row_dict[f"?{var}"] = str(val) if val is not None else None
                    rows.append(row_dict)
                return SparqlResponse(results_json=json.dumps(rows))
            if results.type == "ASK":
                return SparqlResponse(results_json=json.dumps({"boolean": bool(results.askAnswer)}))
            # CONSTRUCT / DESCRIBE — return empty
            return SparqlResponse(results_json="[]")
        except Exception as e:
            logger.debug("SPARQL error: %s | query: %s", e, request.query[:120])
            return SparqlResponse(results_json="[]")

    def HybridSearch(self, request):
        ns = request.namespace or "default"
        g = self._graph(ns)
        q = (request.query or "").lower()
        limit = request.limit or 10

        scored: list[tuple[float, str, str]] = []
        seen: set[str] = set()

        for s, p, o in g:
            uri = str(s)
            if uri in seen:
                continue
            content = f"{s} {p} {o}"
            if q in content.lower():
                # higher score if the query matches the subject URI directly
                score = 1.0 if q in uri.lower() else 0.5
                scored.append((score, uri, content))
                seen.add(uri)

        scored.sort(key=lambda x: x[0], reverse=True)
        return SearchResponse(results=[
            SearchResult(uri=uri, content=content, score=score)
            for score, uri, content in scored[:limit]
        ])
