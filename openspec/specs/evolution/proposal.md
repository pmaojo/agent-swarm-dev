# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

## Motivation & Log Analysis

Based on an empirical analysis of `synapse.log` and execution traces, we have identified significant latency regressions and computational bottlenecks. Specifically, we observed HTTP timeout errors and slow vector embedding insertions (e.g., `error sending request for url (http://localhost:11434/api/embeddings)`) that block the main event loop. To resolve these issues, we identified the three Python modules with the highest computational load:

1. **Analyst Agent** (`sdk/python/agents/analyst.py`) - Handles extensive text processing, string manipulation, clustering, and prompt optimization. The CPU-bound nature of this work blocks the GIL, causing latency spikes.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`) - Manages the complex state machine, parallel execution graph processing, and zero-LLM routing utilizing high-dimensional vector math (Fractal Search V5). The math computations are bottlenecked by Python's single-threaded execution.
3. **LLM Service Gateway** (`sdk/python/lib/cloud_gateways/factory.py` or `sdk/python/lib/llm.py`) - Manages LLM caching, external API requests, and fallback logic. Synchronous I/O operations block concurrent requests.

## Proposal

We propose to migrate these three computationally intensive Python modules into independent Rust microservices. They will be housed within the existing `synapse-engine` workspace. These microservices will interact with the remaining Python agents over gRPC.

<!-- @synapse:rule Convert the computationally heavy Python modules (Analyst Agent, Orchestrator Core, LLM Service Gateway) into independent Rust microservices interacting via gRPC to improve latency and reduce computational load. -->
**Analysis & Evidence:** Our empirical analysis of `synapse.log` directly correlates the observed HTTP timeout errors (`error sending request for url (http://localhost:11434/api/embeddings)`) with blocking I/O operations and CPU-bound tasks in the aforementioned Python modules. By migrating the Analyst Agent, Orchestrator Core, and LLM Service Gateway to Rust, we leverage Tokio's asynchronous runtime to eliminate the GIL bottleneck, thereby preventing the main event loop from blocking during high-latency operations like vector embedding insertions and Fractal Search routing.

## Expected Benefits

* **Concurrency**: Utilizing Rust's `Tokio` asynchronous runtime will eliminate GIL limitations, massively improving the Orchestrator's parallel task management.
* **Performance**: Vector similarity computations for Fractal Search V5 and token parsing in the Analyst agent will execute orders of magnitude faster.
* **Reliability & Latency**: Removing blocking I/O from the Python event loop will prevent the HTTP embedding timeouts observed in the logs.

## Migration Strategy

1. Define strict Protobuf (`.proto`) contracts for each service.
2. Implement the Rust backend using `tonic` and `tokio`.
3. Generate Python bindings using `grpcio-tools`.
4. Update Python agents to act as asynchronous gRPC clients.
