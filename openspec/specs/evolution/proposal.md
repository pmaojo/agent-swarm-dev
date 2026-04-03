# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

## Motivation

As observed in Synapse execution logs and system profiling, the following Python modules suffer from high computational load and latency, likely due to Python GIL and synchronous I/O bottlenecks:
1. **Analyst Agent** (`sdk/python/agents/analyst.py`) - Extensive text processing, clustering, and prompt optimization.
   - `@synapse:rule` Migrate to Rust to offload heavy regex optimizations and text clustering from the Python GIL.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`) - Complex state machine management, parallel execution graph processing, and zero-LLM routing with high-dimensional vector math.
   - `@synapse:rule` Migrate to Rust to enable true multithreaded concurrent task routing and high-performance vector spatial truncation.
3. **LLM Service Gateway** (`sdk/python/lib/cloud_gateways/factory.py` or `sdk/python/lib/llm.py`) - Managing LLM caching, external API requests, and fallback logic.
   - `@synapse:rule` Migrate to Rust to provide asynchronous non-blocking API proxying and high-throughput cache management.

## Proposal

We propose migrating the Analyst Agent, Orchestrator Core, and LLM Service Gateway into dedicated, highly concurrent Rust microservices. By porting these components out of the Python ecosystem, we can leverage Rust's `tokio` asynchronous runtime and `tonic` for gRPC communication, eliminating the Python GIL bottleneck. The new Rust services will act as independent gRPC endpoints. The Analyst service will handle intensive text manipulations and prompt optimization, the Orchestrator service will manage complex state machines and routing, and the LLM Gateway will manage concurrent provider requests and LRU caching.

## Expected Benefits

* **Zero-GIL Concurrency**: True multithreading will enable the Orchestrator to process concurrent sub-agent graphs simultaneously without I/O blocking.
* **Sub-millisecond Latency**: Vector spatial truncation for routing in the Orchestrator and heavy string allocations in the Analyst will see extreme performance boosts, drastically lowering overall request latency.
* **Robust Resilience**: The strict Rust type system and memory safety guarantees will prevent null reference errors during complex multi-stage LLM generation flows.
* **Modular Deployment**: Separating these computational engines allows them to scale horizontally independent of the lighter Python-based orchestration hooks.

## Migration Strategy

1. **Protobuf Contracts**: Author precise `semantic_engine.proto` definitions for the Analyst, Orchestrator, and LLM Gateway services.
2. **Rust Backend**: Construct the services inside the `synapse-engine` workspace utilizing `tonic` for gRPC and `fastembed-rs` for semantic search.
3. **Binding Generation**: Autogenerate Python client bindings via `grpcio-tools` into `sdk/python/agents/synapse_proto`.
4. **Agent Integration**: Refactor the Python agents to initialize non-blocking `grpc` stubs, complete with fallback mechanisms if the backend is temporarily unreachable.
