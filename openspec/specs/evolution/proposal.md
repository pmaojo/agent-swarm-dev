# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

## Motivation

As observed in Synapse execution logs and system profiling, the following Python modules suffer from high computational load and latency, likely due to Python GIL and synchronous I/O bottlenecks:
1. **Analyst Agent** (`sdk/python/agents/analyst.py`) - Extensive text processing, clustering, and prompt optimization.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`) - Complex state machine management, parallel execution graph processing, and zero-LLM routing with high-dimensional vector math.
3. **LLM Service Gateway** (`sdk/python/lib/llm.py`) - Managing LLM caching, external API requests, and fallback logic.

## Proposal

Migrate these three computationally intensive Python modules into independent Rust microservices within the existing `synapse-engine` or a new workspace (e.g., `orchestrator-engine`). These microservices will communicate with the remaining Python ecosystem (or other services) via gRPC, similar to the `codegraph-engine`.

## Expected Benefits

* **Concurrency**: Rust's asynchronous runtime (e.g., Tokio) will significantly improve the Orchestrator's parallel task management ("War Room" mode) without GIL limitations.
* **Performance**: Vector similarity computations (Fractal Search V5 routing) and text processing in the Analyst will execute orders of magnitude faster.
* **Reliability**: Rust's strict type system will reduce runtime errors in complex state transitions.

## Migration Strategy

1. Define Protobuf (`.proto`) contracts for each service's APIs.
2. Implement the Rust gRPC servers using `tonic`.
3. Generate Python gRPC bindings using `grpcio-tools`.
4. Update Python agents/tools to act as gRPC clients (stubs) to these new Rust services.
