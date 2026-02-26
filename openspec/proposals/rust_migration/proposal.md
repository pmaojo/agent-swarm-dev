# Proposal: Migrate Python Code Analysis Modules to Rust Microservices

## Context
The current implementation of `CodeParser`, `CodeGraphIndexer`, and `CodeGraphSlicer` in Python relies on synchronous execution and the Global Interpreter Lock (GIL), which limits performance when processing large repositories or handling concurrent requests. These modules are critical for the "Code Graph" functionality, which powers context awareness, semantic search, and automated refactoring.

## Problem Analysis
1.  **CodeParser (`sdk/python/lib/code_parser.py`)**:
    -   **Heavy CPU Load**: Uses `tree-sitter` (via Python bindings) to parse code into ASTs. While `tree-sitter` is fast, the Python glue code for traversing the tree and extracting symbols adds significant overhead, especially for large files.
    -   **Redundant Parsing**: Files are re-parsed on every request in some flows, leading to wasted CPU cycles.
2.  **CodeGraphIndexer (`sdk/python/lib/code_graph_indexer.py`)**:
    -   **High Latency**: Performs recursive file scanning and synchronous gRPC calls to Synapse for *every* symbol. This results in N+1 query problems and slow indexing times for large codebases.
    -   **Memory Usage**: Loads entire file contents into Python memory before parsing.
3.  **CodeGraphSlicer (`sdk/python/lib/code_graph_slicer.py`)**:
    -   **Complex Logic**: Implements graph traversal and string manipulation to generate "skeleton" views. This is computationally expensive in Python and blocks the main thread.
    -   **Serialization Overhead**: Passing large graph structures between Python and Synapse (via gRPC) incurs serialization/deserialization costs.

## Proposed Solution
Migrate these three modules to a unified **Rust Microservice** (`codegraph-engine`).

### Benefits
1.  **Performance**: Rust's zero-cost abstractions and lack of GIL allow for highly parallelized parsing and indexing. We can use `rayon` for parallel file processing.
2.  **Safety**: Rust's ownership model prevents data races, ensuring thread safety during concurrent graph operations.
3.  **Efficiency**: Direct integration with `tree-sitter` in Rust avoids Python object overhead.
4.  **Scalability**: A standalone gRPC service can be scaled independently of the Python SDK/Orchestrator.

## Microservice Architecture
-   **Name**: `codegraph-engine`
-   **Language**: Rust
-   **Communication**: gRPC (via `tonic`)
-   **Dependencies**:
    -   `tree-sitter`: For parsing.
    -   `tonic`: For gRPC server.
    -   `tokio`: For async runtime.
    -   `serde`: For JSON serialization.

## Migration Strategy
1.  **Phase 1: API Definition**: Define the `codegraph.proto` service contract.
2.  **Phase 2: Rust Implementation**: Implement the `Parse`, `Index`, and `Slice` methods in Rust.
3.  **Phase 3: Python Integration**: Replace the Python implementations in `sdk/python/lib/` with gRPC clients that call the Rust service.
4.  **Phase 4: Deprecation**: Remove the old Python logic once the Rust service is stable.

## Proposed Protobuf Definition (`codegraph.proto`)

```protobuf
syntax = "proto3";

package codegraph.v1;

service CodeGraphService {
  // Parses a file and returns its symbols and relationships
  rpc ParseFile (ParseFileRequest) returns (ParseFileResponse);

  // Indexes a repository (bulk operation)
  rpc IndexRepository (IndexRepositoryRequest) returns (IndexRepositoryResponse);

  // Generates a skeleton view of the code graph based on a target symbol
  rpc SliceGraph (SliceGraphRequest) returns (SliceGraphResponse);
}

message ParseFileRequest {
  string content = 1;
  string language = 2; // e.g., "python", "rust"
  string filepath = 3;
}

message ParseFileResponse {
  repeated Symbol symbols = 1;
}

message Symbol {
  string name = 1;
  string type = 2;
  int32 start_line = 3;
  int32 end_line = 4;
  string hash = 5;
  repeated string calls = 6;
  repeated string inherits_from = 7;
}

message IndexRepositoryRequest {
  string root_path = 1;
  string synapse_host = 2; // Address of the Synapse instance to ingest data into
}

message IndexRepositoryResponse {
  int32 files_processed = 1;
  int32 symbols_indexed = 2;
  repeated string errors = 3;
}

message SliceGraphRequest {
  string target_symbol_uri = 1;
  int32 max_depth = 2;
  string synapse_host = 3; // To query the graph
}

message SliceGraphResponse {
  string context = 1; // The skeleton code
  int64 original_size = 2;
  int64 pruned_size = 3;
  float savings_percent = 4;
}
```
