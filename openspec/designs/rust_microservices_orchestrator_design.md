# Technical Design: Rust Microservices for Orchestrator, Analyst, and LLM Gateway

## Objective
Convert the computationally heavy Python modules (Analyst Agent, Orchestrator Core, LLM Service Gateway) into independent Rust microservices interacting via gRPC. This technical design fulfills the approved OpenSpec proposal for migrating away from Python GIL bottlenecks.

<!-- @synapse:rule Implement independent Rust microservices for Analyst, Orchestrator, and LLM Gateway using Tonic to alleviate Python computational and I/O bottlenecks. -->

## Architecture

### 1. Protobuf Definitions
The new services will be defined in a new package `orchestrator.v1` and compiled using `grpcio-tools`.

```protobuf
syntax = "proto3";
package orchestrator.v1;

service OrchestratorService {
  rpc RouteTask(RouteTaskRequest) returns (RouteTaskResponse);
  rpc ManageStateGraph(StateGraphRequest) returns (StateGraphResponse);
}

service AnalystService {
  rpc OptimizePrompt(OptimizePromptRequest) returns (OptimizePromptResponse);
  rpc ClusterFailures(ClusterFailuresRequest) returns (ClusterFailuresResponse);
}

service LlmGatewayService {
  rpc Complete(LlmCompletionRequest) returns (LlmCompletionResponse);
}
```

### 2. Rust Implementation (`orchestrator-engine` / `synapse-engine`)
- **Frameworks**: Use `tonic` and `tokio` for high-performance, asynchronous gRPC serving.
- **Vector Math**: Integrate `fastembed-rs` to perform the 64d Fractal Search V5 routing computations, completely offloading this from Python.
- **Caching**: Implement a thread-safe LRU cache for the `LlmGatewayService` to minimize redundant API calls.
- **Deployment**: Expose the services on a dedicated port defined via environment variables.

### 3. Python Integration (`sdk/python/agents/orchestrator.py`, etc.)
- **Code Generation**: Use `python -m grpc_tools.protoc` to generate `orchestrator_pb2.py` and `orchestrator_pb2_grpc.py`.
- **Stub Initialization**: Instantiate non-blocking stubs within the Python agents (e.g., `OrchestratorAgent`).
- **Resilience**: Implement asynchronous non-blocking channel checks (e.g., `grpc.channel_ready_future` with a timeout). If the Rust microservice is unavailable, fallback gracefully to the legacy Python implementation or a `None` stub to prevent system halting.

## Impact
- Substantial reduction in CPU time and latency during high concurrency tasks.
- Resolves HTTP timeouts observed in embedding generation.
- Decouples core logic from Python to prepare for broader backend modernization.
