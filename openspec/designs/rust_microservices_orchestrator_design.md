# Technical Design: Rust Microservices for Orchestrator, Analyst, and LLM Gateway

## Objective
Convert the computationally heavy Python modules (Analyst Agent, Orchestrator Core, LLM Service Gateway) into independent Rust microservices interacting via gRPC.

## Architecture

### 1. Protobuf Definitions (`semantic_engine.proto`)
The new services will be integrated into the existing `synapse-engine` gRPC ecosystem. We will expand the protobuf definitions to include robust APIs for our three primary bottlenecks:

```protobuf
syntax = "proto3";
package semantic.engine.v1;

service OrchestratorCoreService {
  rpc FastClassifyStack(StackClassificationRequest) returns (StackClassificationResponse);
  rpc ExecuteTaskGraph(TaskGraphRequest) returns (stream TaskGraphUpdateResponse);
}

service AnalystService {
  rpc OptimizePromptTokens(TokenOptimizationRequest) returns (TokenOptimizationResponse);
  rpc GenerateSemanticClusters(ClusteringRequest) returns (ClusteringResponse);
}

service LlmServiceGateway {
  rpc ProxyCompletion(CompletionRequest) returns (CompletionResponse);
}
```

### 2. Rust Microservices Implementation (`synapse-engine`)
- **Tonic & Tokio**: Services will be bound using `tonic::transport::Server` within the `tokio` async runtime, mapping incoming Python gRPC requests to high-performance, non-blocking Rust native handlers.
- **FastEmbed Integration**: The `OrchestratorCoreService` will utilize the Rust-native `fastembed` crate to compute spatial truncations and high-dimensional vector routing instantly, bypassing the Python GIL.
- **Gateway Caching**: The `LlmServiceGateway` will implement an atomic, thread-safe `moka` LRU cache to slash duplicate inference latencies.

### 3. Python Orchestrator Integration via gRPC (`sdk/python`)
- **Stub Generation**: We will auto-generate Python gRPC bindings (`orchestrator_pb2.py`, `orchestrator_pb2_grpc.py`) using `grpcio-tools`.
- **Dynamic Channel Management**: The `OrchestratorAgent` and `AnalystAgent` will instantiate resilient gRPC channels to the Rust microservices. Crucially, they will utilize `grpc.channel_ready_future` to implement a non-blocking timeout check.
- **Graceful Fallback**: If the Rust engine is unavailable or unbuildable on the target host, the stubs will fallback seamlessly to the legacy Python native logic to ensure uninterrupted Orchestrator operation.

## Impact
- **Latency Collapse**: Token optimization and text clustering latency will drop by an estimated 90% via native Rust string handling in the Analyst microservice.
- **Multithreaded Orchestration**: The Orchestrator will be unblocked to run vastly more parallel LLM generation tasks simultaneously using thread-safe gRPC futures instead of constrained GIL-bound threads.
- **Memory Efficiency**: Utilizing `moka` in the Rust LLM gateway will significantly reduce memory overhead compared to unbounded Python dictionaries.
