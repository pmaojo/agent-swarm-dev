# OpenSpec: Migrate Orchestrator to Rust

## Objective
Migrate computationally heavy Python modules (AnalystAgent, OrchestratorAgent, LLMService) to a Rust microservice (`orchestration-engine`) to improve scalability, reduce latency, and minimize computational overhead.

## Background
The user requested: "Remove python if we have rust replacements". The codebase already includes Python gRPC stubs aiming at `localhost:50054` (Orchestrator), `localhost:50055` (Analyst), and `localhost:50056` (LLM Gateway). However, the corresponding Rust implementations within `synapse-engine/crates/orchestration-engine` do not yet exist.

This spec details the creation of the missing Rust crate and the eventual deprecation of the legacy Python fallback logic.

## Scope
1. **Create Rust Crate (`orchestration-engine`)**
   - Location: `synapse-engine/crates/orchestration-engine/`
   - Technologies: `tonic` (gRPC), `tokio` (Async), `rayon` (CPU-bound tasks).
2. **Implement Microservices**
   - **AnalystService** (`50055`): Implement `ClusterFailures` and `GenerateGoldenRules` focusing on high-performance string matching and clustering.
   - **OrchestratorService** (`50054`): Implement `RouteTask` and `ManageStateGraph` using efficient graph operations and deterministic routing logic.
   - **LlmGatewayService** (`50056`): Implement `Complete` bridging to LLM endpoints and enforcing rate limits/budgets outside the GIL.
3. **Deprecate Python Logic**
   - Once the Rust microservices are functional and validated, remove the Python fallback implementations in `sdk/python/agents/analyst.py`, `sdk/python/agents/orchestrator.py`, and `sdk/python/lib/llm.py`.

## Technical Approach
- Define the gRPC contracts in `synapse-engine/crates/orchestration-engine/proto/orchestration_engine.proto`.
- Set up a multi-server Tokio binary to run all three services concurrently on different ports.
- The `OrchestratorAgent` currently handles complex state management which will be migrated to Tokio state machines.
- The `AnalystAgent` runs CPU-heavy log analysis and pattern matching which will benefit from Rayon parallel iterators.
- Ensure the newly created crate integrates smoothly into the `synapse-engine` workspace and CI pipeline.

## Human Approval
Execution is halted pending human approval to proceed with scaffolding this Rust microservice and modifying the build system.