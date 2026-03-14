# OpenSpec Proposal: Migration of Core Python Modules to Rust Microservices

## 1. Executive Summary

As a Site Reliability Engineer (SRE) analyzing the execution logs in Synapse for the `agent-swarm-dev` repository, it has been identified that the following three Python modules exhibit the highest computational load and latency, becoming bottlenecks for system scalability and performance due to the Python GIL and synchronous I/O operations:
1. **Analyst Agent** (`sdk/python/agents/analyst.py`)
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`)
3. **LLM Service Gateway** (`sdk/python/lib/llm.py`)

This proposal advocates for migrating these modules into independent Rust-based microservices to significantly enhance throughput, reduce latency, and improve overall system reliability.

## 2. Problem Statement

The current implementation relies heavily on Python for critical paths involving prompt optimization, state machine orchestration (including graph-driven "War Room" and "Council" modes), and interactions with large language models (LLMs). Execution logs indicate that:
* The **Analyst Agent** suffers from high CPU utilization when performing intensive token-reduction tasks (e.g., `optimize_prompt`).
* The **Orchestrator Core** experiences latency spikes when evaluating routing logic ("Zero-LLM Routing" and "Circuit Breaker") and managing the complex state machine.
* The **LLM Service Gateway** encounters throughput limitations due to concurrent requests being blocked by the synchronous nature of the current architecture or single-threaded limits.

## 3. Proposed Solution

We propose decomposing these three monolithic modules into distinct, highly concurrent Rust microservices:
1. `analyst-engine`: A dedicated Rust microservice handling prompt optimization and token reduction.
2. `orchestrator-engine`: A high-performance state machine for routing and task orchestration.
3. `llm-gateway-engine`: An asynchronous Rust gateway to interact with LLMs and efficiently handle caching and rate-limiting.

These microservices will communicate with the remaining Python ecosystem (if any) and each other via gRPC, offering a robust, statically typed, and extremely fast contract mechanism.

## 4. Expected Benefits
* **Performance:** Substantial reduction in execution latency by eliminating GIL contention.
* **Concurrency:** Rust's async runtime (e.g., Tokio) will effortlessly handle thousands of concurrent LLM requests and orchestration states.
* **Reliability:** Strict type checking and memory safety guarantees from Rust will minimize runtime errors and reduce the risk of out-of-memory or null-pointer exceptions in production.

## 5. Next Steps
Upon approval of this OpenSpec proposal, the engineering team will:
1. Draft a comprehensive Technical Design Document detailing the gRPC integration with the remaining components, Protobuf schemas, and the migration strategy.
2. Initialize the Rust project structures within the `vendor/` or top-level directories.
3. Begin iterative implementation and testing.

Please review and approve to proceed with the technical design phase.