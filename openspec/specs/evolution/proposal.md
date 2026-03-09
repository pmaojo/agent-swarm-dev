# OpenSpec Proposal: Evolution of Core Python Modules to Rust Microservices

## Context
Analysis of the Synapse execution logs indicates that the **Analyst Agent**, **Orchestrator Core**, and **LLM Service Gateway** are currently the Python modules with the highest computational load and latency. These modules handle critical and performance-sensitive paths within the system:
- **Analyst Agent:** Performs computationally heavy text and JSON processing (like `cluster_failures` and `optimize_prompt`).
- **Orchestrator Core:** Manages the graph-driven workflow and can be bottlenecked by Python's Global Interpreter Lock (GIL) and synchronous I/O.
- **LLM Service Gateway:** Interacts with multiple providers and is affected by high latencies during concurrent requests.

## Proposal
We propose migrating these 3 critical modules from Python to independent Rust-based microservices. This aligns with our prior evolution strategy (e.g., `codegraph-engine`).

### Benefits
1. **Concurrency and Scaling:** Rust's async runtime will allow the Orchestrator Core and LLM Service Gateway to handle high concurrency effectively without GIL contention.
2. **Computational Performance:** The Analyst Agent will execute intensive processing tasks significantly faster with memory safety guarantees.
3. **Reduced Latency:** Moving off synchronous Python I/O bounds will reduce end-to-end processing delays.

### Architecture Overview
- **Independent Services:** Each module will be its own Rust microservice (e.g., `analyst-engine`, `orchestrator-engine`, `gateway-engine`).
- **Communication:** Services will communicate via gRPC, adhering to our established schema.
- **Integration:** The existing Python runtime will call these Rust microservices through generated gRPC stubs.
