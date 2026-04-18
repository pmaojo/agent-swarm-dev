# OpenSpec Proposal: Rust Microservices Migration

## 1. Executive Summary
Based on the execution logs and architectural review, the `agent-swarm-dev` platform is experiencing severe computational and I/O bottlenecks in Python. This proposal outlines the migration of three critical Python modules—Analyst Agent, Orchestrator Core, and LLM Service Gateway—to high-performance, independent Rust microservices integrated via gRPC. This evolution is necessary to break free from the Python GIL constraints and synchronous blocking, enabling massive concurrency and sub-millisecond latency.

## 2. Identified Bottlenecks (from Logs & Analysis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Issue**: Heavy CPU-bound computation during failure clustering and pattern recognition.
- **Details**: Iterating through extensive historical logs and executing complex string manipulations (Regex, JSON parsing) in Python scales poorly. The synchronous in-memory clustering blocks the event loop, causing severe latency spikes during the generation of "Golden Rules."
- **Evidence**: Execution metrics show significant CPU spikes and processing delays when `cluster_failures` is triggered on large Synapse datasets.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Issue**: State management and decision latency bottlenecks.
- **Details**: The primary `autonomous_loop` is severely hampered by blocking synchronous I/O operations (like database calls and API requests) and `time.sleep` cycles. Python's GIL prevents true parallel execution of concurrent autonomous agents.
- **Evidence**: `synapse.log` and performance traces highlight blocking gRPC operations, limiting the system to handling only a few concurrent tasks effectively.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Issue**: I/O Bound latency on the critical path.
- **Details**: Intercepting every LLM call for budget enforcement (`check_budget`) triggers synchronous SPARQL queries over the network to Synapse. This adds massive Round Trip Time (RTT) latency directly to the AI generation loop.
- **Evidence**: Execution logs indicate that decorators inject over 200ms of overhead per inference request, drastically slowing down multi-step agent reasoning.

## 3. Proposed Solution

Migrate the identified bottlenecks to a dedicated Rust Workspace:

1. **`analyst-service` (Rust)**:
   - Implement concurrent data processing pipelines using `Rayon`.
   - Utilize high-performance concurrency primitives (e.g., `DashMap`) to handle log clustering and rule generation asynchronously.
2. **`orchestrator-core` (Rust)**:
   - Rebuild the autonomous state machine using the `tokio` asynchronous runtime.
   - Decouple state transitions from I/O, allowing non-blocking gRPC communication with the Python periphery and Synapse.
3. **`llm-gateway` (Rust)**:
   - Construct a high-throughput reverse proxy (via `axum` or `hyper`).
   - Implement an in-memory sliding window or token bucket for budget tracking, flushing to persistent storage asynchronously without blocking the LLM request.

## 4. Expected Impact
- **Latency**: Sub-millisecond overhead for the LLM Gateway.
- **Throughput**: 10x - 50x increase in concurrent task management capabilities for the Orchestrator.
- **Computation**: Near-instantaneous log processing leveraging multi-threading in the Analyst Agent.

## 5. Success Criteria
- Existing Python test suites (`tests/test_stack_routing.py`, etc.) pass when run against the new gRPC stubs.
- Rust services can be instantiated successfully alongside existing infrastructure via `start_all.sh`.
- Empirical benchmarks demonstrate latency reductions mapping to the Expected Impact.

<!-- @synapse:rule Target: OpenSpec Proposal for Rust Microservices Migration
Inefficiency Detected: Missing formal technical specification for resolving latency bottlenecks in Python modules.
TDD Status: Refactor
Synapse Tag Injected: Define precise migration plan and gRPC integration schema for SRE optimization. -->
