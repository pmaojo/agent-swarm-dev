# Technical Design: Rust Microservices for Core Orchestration and Analysis

## Overview
This document outlines the technical design for migrating three critical, compute-heavy Python components—**Analyst Agent**, **Orchestrator Core**, and **LLM Service Gateway**—into highly concurrent, performant Rust microservices. This migration specifically targets the computational and latency bottlenecks present in the current Python implementations due to the GIL and synchronous I/O operations.

## Target Microservices

1. **Analyst Engine (`analyst-engine`)**
   - **Role:** Handles heavy text and JSON processing (`cluster_failures`, `optimize_prompt`, log analysis).
   - **Architecture:** Stateless processing worker pool. Uses efficient deserialization (`serde_json`) and token/text management in Rust.
   - **gRPC Interface:**
     - `rpc OptimizePrompt(PromptRequest) returns (PromptResponse)`
     - `rpc ClusterFailures(FailureLogsRequest) returns (ClusterResponse)`

2. **Orchestrator Engine (`orchestrator-engine`)**
   - **Role:** Manages the graph-driven workflow state machine, coordinating tasks between agents in 'War Room' (Parallel) and 'Council' (Sequential) modes.
   - **Architecture:** Asynchronous state manager. Connects natively to Synapse graph storage to update `swarm:Task` and `swarm:LessonLearned` triples efficiently.
   - **gRPC Interface:**
     - `rpc StepWorkflow(WorkflowRequest) returns (WorkflowResponse)`
     - `rpc RegisterTask(TaskRequest) returns (TaskResponse)`

3. **LLM Gateway Engine (`gateway-engine`)**
   - **Role:** Routes and caches prompt requests to external providers (Claude, Codex, Jules). Applies load-balancing, rate-limiting, and circuit-breaking.
   - **Architecture:** Asynchronous networking layer (e.g., Tokio, reqwest). Maintains an LRU cache natively in memory to reduce external API latency.
   - **gRPC Interface:**
     - `rpc RequestCompletion(LLMRequest) returns (LLMResponse)`
     - `rpc GetGatewayStatus(StatusRequest) returns (StatusResponse)`

## Orchestrator Integration (Python -> Rust)

To ensure a smooth transition, the existing Python application will become a thin client for these services.

### Communication Protocol
All communication between the Python SDK/Legacy Agents and the new Rust microservices will occur over **gRPC**.

1. **Protobuf Definitions:**
   - Defined in `orchestration.proto` and `analysis.proto`.
   - Python stubs will be generated in `sdk/python/agents/synapse_proto/`.

2. **Python Client Stub (OrchestratorAgent):**
   ```python
   # sdk/python/agents/orchestrator.py
   import grpc
   from agents.synapse_proto import orchestration_pb2_grpc

   class OrchestratorAgent:
       def __init__(self, target_address="localhost:50052"):
           # Non-blocking stub with a timeout fallback
           try:
               self.channel = grpc.insecure_channel(target_address)
               grpc.channel_ready_future(self.channel).result(timeout=2.0)
               self.stub = orchestration_pb2_grpc.OrchestratorEngineStub(self.channel)
           except grpc.FutureTimeoutError:
               self.stub = None
               print("Warning: Rust Orchestrator Engine unreachable. Falling back.")

       def step(self, workflow_state):
           if self.stub:
               # Call Rust Microservice
               response = self.stub.StepWorkflow(...)
               return response
           else:
               # Fallback to legacy Python logic
               pass
   ```

### Execution Strategy
1. **gRPC Server Configuration:**
   - The Rust services will bind to environment variables (`ORCHESTRATOR_GRPC_PORT`, default 50052, etc.) to ensure flexibility and avoid conflicts with the existing Synapse engine (50051).
2. **Asynchronous Runtime:**
   - Services will be built on `tokio` for handling thousands of concurrent gRPC requests, essential for the 'War Room' parallel execution mode.
3. **Robust Fallbacks:**
   - Python callers (e.g., `OrchestratorAgent`) will implement non-blocking connection checks. If the Rust stub is `None` (unavailable), execution gracefully degrades or pauses.

## Implementation Steps
1. Define the `.proto` service and message contracts.
2. Bootstrap the 3 Rust Cargo workspaces (`analyst-engine`, `orchestrator-engine`, `gateway-engine`).
3. Generate Python and Rust gRPC stubs.
4. Implement the core logic inside the Rust microservices.
5. Update `sdk/python/agents/` Python modules to call the Rust endpoints.
6. Add comprehensive unit and integration tests mocking the gRPC stubs.
