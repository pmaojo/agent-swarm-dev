# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

## Motivation

Based on an empirical analysis of Synapse execution logs and system profiling, we have identified severe computational bottlenecks within the `agent-swarm-dev` repository. Specifically, three Python modules suffer from high computational load and latency, primarily constrained by the Python Global Interpreter Lock (GIL) and synchronous I/O operations:

1. **Analyst Agent** (`sdk/python/agents/analyst.py`)
   - **Inefficiency:** Extensive text processing, clustering of failure modes, and prompt optimization routines.
   - **Impact:** High CPU utilization and token processing delays during complex analytical tasks.

2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`)
   - **Inefficiency:** Complex state machine management, parallel execution graph processing, and zero-LLM routing involving high-dimensional vector math (Fractal Search V5).
   - **Impact:** Severe latency in task distribution and routing decisions, especially under high concurrency ("War Room" scenarios).

3. **LLM Service Gateway** (`sdk/python/lib/llm.py` & `sdk/python/lib/cloud_gateways/factory.py`)
   - **Inefficiency:** Managing large-scale LLM caching, handling external API requests, and executing dynamic fallback logic.
   - **Impact:** I/O blocking and queuing delays, exacerbating overall system latency during heavy inference workloads.

## Proposal

We propose to migrate these three computationally intensive Python modules into independent Rust microservices. These services could be integrated within the existing `synapse-engine` workspace or scaffolded in a new workspace (e.g., `orchestrator-engine`).

By converting these modules to Rust, we will leverage its performance characteristics and memory safety, allowing the remaining Python ecosystem to offload heavy computations via gRPC, similar to the successful implementation of the `codegraph-engine`.

## Expected Benefits

* **Concurrency & Scalability**: Rust's asynchronous runtime (e.g., `tokio`) will significantly improve the Orchestrator's parallel task management by entirely bypassing Python GIL limitations.
* **Performance Boost**: Vector similarity computations for routing and intensive text processing algorithms in the Analyst Agent will execute orders of magnitude faster.
* **Reliability & Type Safety**: Rust's strict compiler and type system will drastically reduce runtime errors in complex state transitions and API gateway fallbacks.

## Migration Strategy

1. **Contract Definition**: Define strict Protobuf (`.proto`) contracts for each service's APIs to ensure seamless integration.
2. **Implementation**: Implement the Rust gRPC servers utilizing `tonic`.
3. **Bindings Generation**: Generate Python gRPC bindings using `grpcio-tools`.
4. **Integration**: Update existing Python agents and tools to act as lightweight gRPC clients (stubs) interfacing with the new Rust microservices.

*Note: Following the workflow mandate, this proposal halts here for human approval before proceeding to the detailed technical design of the gRPC integration.*
