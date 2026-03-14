# Technical Design: Rust Microservices Migration for Python Components

## Objective
This document outlines the technical design for migrating three computationally intensive and latency-sensitive Python modules (Analyst Agent, Orchestrator Core, and LLM Service Gateway) to independent Rust microservices communicating via gRPC. This architecture addresses the Python Global Interpreter Lock (GIL) limitations and aims to enhance system performance, scalability, and responsiveness within the `agent-swarm-dev` repository.

## Components and Responsibilities

### 1. Analyst Engine (Rust Service)
**Responsibility**: Text processing, prompt optimization, and large dataset analysis.
**Key Features**:
*   **Prompt Optimization**: Implementing token-efficient algorithms to safely collapse redundant spacing and newlines, preserving indentation logic, ensuring accurate code and stack trace structures before LLM submission.
*   **Log Processing**: Implementing optimized parsing logic (e.g., extracting first elements from large JSON arrays without full serialization overhead) to identify clusters and reduce CPU load.
*   **Data Aggregation**: Efficiently aggregating and summarizing large volumes of diagnostic data.

### 2. Orchestration Engine (Rust Service)
**Responsibility**: Core task routing, workflow management, and state machine orchestration.
**Key Features**:
*   **Workflow Execution**: Managing complex state transitions and supporting sophisticated execution modes like 'War Room' (Parallel) and 'Council' (Sequential).
*   **Zero-LLM Routing**: Integrating with Fractal Search V5 (using an optimized spatial truncation approach, e.g., `prefix_len=64`) for high-speed, vector similarity-based task assignments before falling back to full-resolution or LLM-based execution.
*   **Circuit Breaker & Bankruptcy Protection**: Enforcing robust controls based on `swarm:LessonLearned` entries and token budget thresholds to prevent system overloads or wasteful processing.

### 3. LLM Gateway Service (Rust Service)
**Responsibility**: Managing external LLM API communications, caching, and rate-limiting.
**Key Features**:
*   **High-Performance In-Memory Cache**: Implementing an LRU cache mechanism to minimize redundant API calls and reduce latency.
*   **Connection Pooling**: Managing persistent connections to external LLM providers (Claude, Codex, etc.) efficiently.
*   **Provider Selection Strategy**: Dynamic selection of LLM models based on real-time performance metrics and stack specialization, interfacing with the Synapse semantic engine.

## Inter-Service Communication via gRPC

The microservices will communicate with each other and the existing Python components using gRPC and Protocol Buffers. This approach ensures a strongly typed, language-agnostic, and highly performant communication layer.

### Protobuf Definitions
New `.proto` files will be created for each service to define their respective RPC methods and message structures. For example:
*   `analyst.proto`: Defining methods like `OptimizePrompt` and `ClusterFailures`.
*   `orchestrator.proto`: Defining methods like `RouteTask` and `GetWorkflowState`.
*   `llm_gateway.proto`: Defining methods like `GenerateCompletion` and `ClearCache`.

### Integration with Python Orchestrator
To maintain backward compatibility and facilitate a phased rollout, the existing Python Orchestrator (`sdk/python/agents/orchestrator.py`) will be adapted to act as a client to these new Rust services.

1.  **gRPC Client Generation**: The existing `.proto` definitions will be compiled into Python code using `grpc_tools.protoc`, generating the necessary stubs (e.g., `analyst_pb2.py`, `analyst_pb2_grpc.py`). These will be placed in the `sdk/python/agents/synapse_proto/` directory.
2.  **Non-Blocking Connections**: The Python client logic will use asynchronous or non-blocking mechanisms (e.g., `grpc.channel_ready_future` with a timeout) when connecting to the Rust gRPC channels.
3.  **Graceful Fallbacks**: If a Rust service is unavailable, the Python client will gracefully fall back to local (legacy) execution paths or return a clear error, preventing hard crashes.

## Deployment and Infrastructure
*   Each Rust service will be packaged as a standalone binary within a Docker container.
*   Configuration will be managed via environment variables (e.g., specifying port numbers like `SYNAPSE_GRPC_PORT=50051`).
*   The deployment structure will align with the existing `docker-compose.yml` or standard Kubernetes manifests used for the repository, ensuring seamless integration with existing services like FastEmbed, Synapse server, and Swarm Gateway.

## Testing Strategy
*   **Unit Tests**: Comprehensive unit tests within the Rust ecosystem for business logic.
*   **Integration Tests**: Validating gRPC communication between Python clients and Rust servers, employing mocking strategies in Python test suites (e.g., mocking the `_pb2` and `_pb2_grpc` modules).
*   **Performance Tests**: Establishing benchmarks to measure latency and throughput improvements, ensuring the migration meets its performance objectives.
