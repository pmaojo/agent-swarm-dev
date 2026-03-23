# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

## SRE Analysis

Based on the analysis of the agent-swarm-dev repository and Synapse execution logs, the following 3 Python modules exhibit the highest computational load and latency. This is primarily due to the Python GIL limiting concurrency and synchronous I/O bottlenecks:
1. **Analyst Agent** (`sdk/python/agents/analyst.py`) - Extensive text processing, clustering, and prompt optimization tasks block the event loop.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`) - High-dimensional vector math for Zero-LLM routing, parallel execution graph processing, and complex state machine management cause latency spikes.
3. **LLM Service Gateway** (`sdk/python/lib/cloud_gateways/factory.py` or `sdk/python/lib/llm.py`) - Managing LLM caching and external API requests synchronously impacts overall system throughput.

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
