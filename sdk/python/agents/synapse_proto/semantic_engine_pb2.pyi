from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SearchMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VECTOR_ONLY: _ClassVar[SearchMode]
    GRAPH_ONLY: _ClassVar[SearchMode]
    HYBRID: _ClassVar[SearchMode]

class ReasoningStrategy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NONE: _ClassVar[ReasoningStrategy]
    RDFS: _ClassVar[ReasoningStrategy]
    OWLRL: _ClassVar[ReasoningStrategy]
VECTOR_ONLY: SearchMode
GRAPH_ONLY: SearchMode
HYBRID: SearchMode
NONE: ReasoningStrategy
RDFS: ReasoningStrategy
OWLRL: ReasoningStrategy

class SparqlRequest(_message.Message):
    __slots__ = ("query", "namespace")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    query: str
    namespace: str
    def __init__(self, query: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class SparqlResponse(_message.Message):
    __slots__ = ("results_json",)
    RESULTS_JSON_FIELD_NUMBER: _ClassVar[int]
    results_json: str
    def __init__(self, results_json: _Optional[str] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class Provenance(_message.Message):
    __slots__ = ("source", "timestamp", "method")
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    source: str
    timestamp: str
    method: str
    def __init__(self, source: _Optional[str] = ..., timestamp: _Optional[str] = ..., method: _Optional[str] = ...) -> None: ...

class Triple(_message.Message):
    __slots__ = ("subject", "predicate", "object", "provenance", "embedding")
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    PREDICATE_FIELD_NUMBER: _ClassVar[int]
    OBJECT_FIELD_NUMBER: _ClassVar[int]
    PROVENANCE_FIELD_NUMBER: _ClassVar[int]
    EMBEDDING_FIELD_NUMBER: _ClassVar[int]
    subject: str
    predicate: str
    object: str
    provenance: Provenance
    embedding: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, subject: _Optional[str] = ..., predicate: _Optional[str] = ..., object: _Optional[str] = ..., provenance: _Optional[_Union[Provenance, _Mapping]] = ..., embedding: _Optional[_Iterable[float]] = ...) -> None: ...

class IngestRequest(_message.Message):
    __slots__ = ("triples", "namespace")
    TRIPLES_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    triples: _containers.RepeatedCompositeFieldContainer[Triple]
    namespace: str
    def __init__(self, triples: _Optional[_Iterable[_Union[Triple, _Mapping]]] = ..., namespace: _Optional[str] = ...) -> None: ...

class IngestFileRequest(_message.Message):
    __slots__ = ("file_path", "namespace")
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    file_path: str
    namespace: str
    def __init__(self, file_path: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class IngestResponse(_message.Message):
    __slots__ = ("nodes_added", "edges_added")
    NODES_ADDED_FIELD_NUMBER: _ClassVar[int]
    EDGES_ADDED_FIELD_NUMBER: _ClassVar[int]
    nodes_added: int
    edges_added: int
    def __init__(self, nodes_added: _Optional[int] = ..., edges_added: _Optional[int] = ...) -> None: ...

class NodeRequest(_message.Message):
    __slots__ = ("node_id", "namespace", "direction", "depth", "edge_filter", "limit_per_layer", "scoring_strategy", "node_type_filter")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    EDGE_FILTER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PER_LAYER_FIELD_NUMBER: _ClassVar[int]
    SCORING_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    NODE_TYPE_FILTER_FIELD_NUMBER: _ClassVar[int]
    node_id: int
    namespace: str
    direction: str
    depth: int
    edge_filter: str
    limit_per_layer: int
    scoring_strategy: str
    node_type_filter: str
    def __init__(self, node_id: _Optional[int] = ..., namespace: _Optional[str] = ..., direction: _Optional[str] = ..., depth: _Optional[int] = ..., edge_filter: _Optional[str] = ..., limit_per_layer: _Optional[int] = ..., scoring_strategy: _Optional[str] = ..., node_type_filter: _Optional[str] = ...) -> None: ...

class NeighborResponse(_message.Message):
    __slots__ = ("neighbors",)
    NEIGHBORS_FIELD_NUMBER: _ClassVar[int]
    neighbors: _containers.RepeatedCompositeFieldContainer[Neighbor]
    def __init__(self, neighbors: _Optional[_Iterable[_Union[Neighbor, _Mapping]]] = ...) -> None: ...

class Neighbor(_message.Message):
    __slots__ = ("node_id", "edge_type", "uri", "direction", "depth", "score")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    EDGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    node_id: int
    edge_type: str
    uri: str
    direction: str
    depth: int
    score: float
    def __init__(self, node_id: _Optional[int] = ..., edge_type: _Optional[str] = ..., uri: _Optional[str] = ..., direction: _Optional[str] = ..., depth: _Optional[int] = ..., score: _Optional[float] = ...) -> None: ...

class SearchRequest(_message.Message):
    __slots__ = ("query", "limit", "namespace", "prefix_len")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    PREFIX_LEN_FIELD_NUMBER: _ClassVar[int]
    query: str
    limit: int
    namespace: str
    prefix_len: int
    def __init__(self, query: _Optional[str] = ..., limit: _Optional[int] = ..., namespace: _Optional[str] = ..., prefix_len: _Optional[int] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[SearchResult]
    def __init__(self, results: _Optional[_Iterable[_Union[SearchResult, _Mapping]]] = ...) -> None: ...

class SearchResult(_message.Message):
    __slots__ = ("node_id", "score", "content", "uri")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    node_id: int
    score: float
    content: str
    uri: str
    def __init__(self, node_id: _Optional[int] = ..., score: _Optional[float] = ..., content: _Optional[str] = ..., uri: _Optional[str] = ...) -> None: ...

class HybridSearchRequest(_message.Message):
    __slots__ = ("query", "namespace", "vector_k", "graph_depth", "mode", "limit", "prefix_len")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    VECTOR_K_FIELD_NUMBER: _ClassVar[int]
    GRAPH_DEPTH_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_LEN_FIELD_NUMBER: _ClassVar[int]
    query: str
    namespace: str
    vector_k: int
    graph_depth: int
    mode: SearchMode
    limit: int
    prefix_len: int
    def __init__(self, query: _Optional[str] = ..., namespace: _Optional[str] = ..., vector_k: _Optional[int] = ..., graph_depth: _Optional[int] = ..., mode: _Optional[_Union[SearchMode, str]] = ..., limit: _Optional[int] = ..., prefix_len: _Optional[int] = ...) -> None: ...

class ResolveRequest(_message.Message):
    __slots__ = ("content", "namespace")
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    content: str
    namespace: str
    def __init__(self, content: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class ResolveResponse(_message.Message):
    __slots__ = ("node_id", "found")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    FOUND_FIELD_NUMBER: _ClassVar[int]
    node_id: int
    found: bool
    def __init__(self, node_id: _Optional[int] = ..., found: bool = ...) -> None: ...

class EmptyRequest(_message.Message):
    __slots__ = ("namespace",)
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    namespace: str
    def __init__(self, namespace: _Optional[str] = ...) -> None: ...

class TriplesResponse(_message.Message):
    __slots__ = ("triples",)
    TRIPLES_FIELD_NUMBER: _ClassVar[int]
    triples: _containers.RepeatedCompositeFieldContainer[Triple]
    def __init__(self, triples: _Optional[_Iterable[_Union[Triple, _Mapping]]] = ...) -> None: ...

class ReasoningRequest(_message.Message):
    __slots__ = ("namespace", "strategy", "materialize")
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    MATERIALIZE_FIELD_NUMBER: _ClassVar[int]
    namespace: str
    strategy: ReasoningStrategy
    materialize: bool
    def __init__(self, namespace: _Optional[str] = ..., strategy: _Optional[_Union[ReasoningStrategy, str]] = ..., materialize: bool = ...) -> None: ...

class ReasoningResponse(_message.Message):
    __slots__ = ("success", "triples_inferred", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    TRIPLES_INFERRED_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    triples_inferred: int
    message: str
    def __init__(self, success: bool = ..., triples_inferred: _Optional[int] = ..., message: _Optional[str] = ...) -> None: ...
