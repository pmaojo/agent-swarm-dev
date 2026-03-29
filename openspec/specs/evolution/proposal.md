# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

**Author:** SRE Team (Agent Jules)
**Date:** 2025-03-29
**Status:** Proposed

## Motivation

As observed in system profiling and execution logs, several Python modules suffer from high computational load and latency. After analyzing the system architecture, the following 3 Python modules have been identified as the most computationally intensive and are constrained by the Python GIL and synchronous I/O bottlenecks:

1. **Analyst Agent** (`sdk/python/agents/analyst.py`) - Incurs high CPU utilization and latency due to extensive text processing, clustering, and prompt optimization operations.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`) - Experiences parallel execution bottlenecks during "War Room" mode due to GIL limitations while managing complex state machines and performing zero-LLM routing with high-dimensional vector math.
3. **LLM Service Gateway** (`sdk/python/lib/cloud_gateways/factory.py` or `sdk/python/lib/llm.py`) - Introduces synchronous I/O overhead and latency when managing LLM caching, external API requests, dynamic retry logic, and fallback mechanisms.

## Proposal

Migrate these three computationally intensive Python modules into independent Rust microservices within the existing `synapse-engine` or a new workspace (e.g., `orchestrator-engine`). These microservices will communicate with the remaining Python ecosystem (or other services) via gRPC, similar to the `codegraph-engine`.

## Expected Benefits

* **Concurrency:** Rust's asynchronous runtime (e.g., Tokio) will significantly improve the Orchestrator's parallel task management without GIL limitations, natively supporting high-throughput event loops.
* **Performance:** Vector similarity computations (Fractal Search V5 routing) and text processing in the Analyst will execute orders of magnitude faster due to zero-cost abstractions and compiled native code.
* **Reliability:** Rust's strict type system and memory safety guarantees will eliminate runtime errors common in complex state transitions.

## Migration Strategy

1. Define Protobuf (`.proto`) contracts for each service's APIs.
2. Implement the Rust gRPC servers using `tonic`.
3. Generate Python gRPC bindings using `grpcio-tools`.
4. Update Python agents/tools to act as gRPC clients (stubs) to these new Rust services.

## Next Step

If this proposal is approved, proceed to the detailed technical design phase to architect the gRPC interfaces and the integration strategy with the Orchestrator.
