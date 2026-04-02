# OpenSpec Proposal: Migrating Computationally Heavy Python Modules to Rust

<!-- @synapse:rule Identify the 3 Python modules with the highest computational load or latency for Rust migration to overcome GIL limits. -->

## SRE Log Analysis and Identification

As an SRE analyzing the `agent-swarm-dev` repository and the Synapse execution logs, I have identified the three Python modules with the highest computational load and latency bottlenecks. My findings are based on empirical log analysis which highlighted extensive timeouts, high latency during synchronous I/O, and CPU-bound delays:

1. **Analyst Agent** (`sdk/python/agents/analyst.py`): Identified as a major bottleneck due to its extensive text processing, complex clustering algorithms, and synchronous prompt optimization loops that heavily tax the CPU.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`): The logs revealed latency spikes during complex state machine management and parallel execution graph processing. Its zero-LLM routing with high-dimensional vector math is constrained by the Python GIL.
3. **LLM Service Gateway** (`sdk/python/lib/llm.py` and `sdk/python/lib/cloud_gateways/factory.py`): High latency was detected in external API requests (e.g., embeddings and LLM completions), largely due to blocking I/O and synchronous LLM caching/fallback logic management.

## Motivation

As observed in Synapse execution logs and system profiling, the above Python modules suffer from high computational load and latency, primarily due to Python GIL and synchronous I/O bottlenecks.

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
