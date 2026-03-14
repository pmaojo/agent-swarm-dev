# Technical Design: Rust Microservices for Orchestrator, Analyst, and LLM Gateway

## Objective
Convert the computationally heavy Python modules (Analyst Agent, Orchestrator Core, LLM Service Gateway) into independent Rust microservices interacting via gRPC.

## Architecture

### 1. Protobuf Definitions
The new services will be defined in a new package, e.g., `orchestrator.v1`.

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
- Use `tonic` and `tokio` for async gRPC serving.
- Integrate `fastembed-rs` (if available, or rust equivalents) for vector math.
- Implement LRU caching for the `LlmGatewayService`.
- Deploy as independent binaries or a unified backend service.

### 3. Python Integration (`sdk/python/agents/orchestrator.py`, etc.)
- Use `grpc_tools.protoc` to generate `orchestrator_pb2.py` and `orchestrator_pb2_grpc.py`.
- Instantiate stubs, similar to the `CodeGraphService` integration.
- Replace internal logic with stub calls to the Rust server. Provide asynchronous non-blocking channel checks.

## Impact
- Substantial reduction in CPU time during high concurrency tasks.
- Improved latency in the critical path (Analyst token collapsing, LLM routing).
- Decouples core logic from Python to prepare for broader backend modernization.
