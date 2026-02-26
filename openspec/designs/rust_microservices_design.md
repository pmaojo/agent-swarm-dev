# Technical Design: Rust Microservices for CodeGraph Engine

## Overview
This document outlines the architecture for migrating the Python-based `CodeParser`, `CodeGraphIndexer`, and `CodeGraphSlicer` modules to a unified Rust microservice, `codegraph-engine`. The goal is to improve performance, scalability, and type safety by leveraging Rust's concurrency model and zero-cost abstractions.

## Architecture

### Components
1.  **CodeGraph Engine (Rust)**:
    -   A standalone gRPC server built with `tonic`.
    -   Uses `tree-sitter` bindings for high-performance parsing.
    -   Handles concurrent file processing and indexing.
    -   Exposes `ParseFile`, `IndexRepository`, and `SliceGraph` RPC methods.

2.  **Orchestrator Integration (Python)**:
    -   The Orchestrator (`sdk/python/agents/orchestrator.py`) will act as a client to the `codegraph-engine`.
    -   Existing Python classes (`CodeParser`, `CodeGraphIndexer`, `CodeGraphSlicer`) will be refactored to delegate logic to the gRPC service.
    -   Fallback logic: If the `codegraph-engine` is unavailable, the Python implementation can serve as a backup (optional, or we can enforce the service dependency).

### Data Flow
1.  **Parsing**: The client sends file content (or path) to `ParseFile`. The engine parses it using `tree-sitter` and returns a structured list of symbols and relationships.
2.  **Indexing**: The client triggers `IndexRepository`. The engine recursively scans the directory, parses files in parallel (using `rayon`), and ingests the results directly into Synapse via its own gRPC connection or returns the data to the client for ingestion. *Decision: Engine ingests directly to Synapse for efficiency.*
3.  **Slicing**: The client requests a slice for a specific symbol URI via `SliceGraph`. The engine queries Synapse (if needed) or uses cached graph data to construct the skeleton view.

## Interfaces
The communication will be defined by `codegraph-engine/proto/codegraph.proto`.

```protobuf
syntax = "proto3";

package codegraph.v1;

service CodeGraphService {
  rpc ParseFile (ParseFileRequest) returns (ParseFileResponse);
  rpc IndexRepository (IndexRepositoryRequest) returns (IndexRepositoryResponse);
  rpc SliceGraph (SliceGraphRequest) returns (SliceGraphResponse);
}

// ... (See Proposal for message definitions)
```

## Implementation Plan
1.  **Setup**: Initialize `codegraph-engine` as a Cargo workspace member.
2.  **Proto**: Define `codegraph.proto`.
3.  **Server**: Implement the gRPC server in `main.rs`.
4.  **Logic**: Port parsing logic from Python to Rust using `tree-sitter` crates.
5.  **Client**: Update Python SDK to use the generated gRPC client.

## Security
-   The service will run in the same trusted network as the Orchestrator and Synapse.
-   No external access exposed.
-   Standard gRPC TLS can be enabled if required.

## Performance Targets
-   **Parsing**: < 10ms per file (vs ~50-100ms in Python).
-   **Indexing**: Full repo index in < 5s for 10k files.
-   **Slicing**: < 20ms response time.
