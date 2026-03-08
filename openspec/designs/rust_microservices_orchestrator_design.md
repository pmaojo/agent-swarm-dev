# Diseño Técnico: System Performance Rust Microservices

**Autor:** SRE Team (Agent Jules)
**Fecha:** 2025-02-17
**Estado:** Draft

## 1. Visión General

Este documento detalla la arquitectura técnica para migrar los tres componentes de Python (`Analyst Agent`, `Orchestrator Core` y `LLM Service Gateway`) con mayor carga computacional y latencia a microservicios en Rust. El objetivo principal es eliminar el overhead del GIL de Python, reducir la latencia de red y mejorar significativamente la escalabilidad del sistema.

## 2. Arquitectura del Sistema

Se propone la creación de tres microservicios independientes integrados mediante gRPC.

```mermaid
graph TD
    subgraph Python SDK
        Agent[Other Agents]
        PythonOrch[Orchestrator Client Stub]
        PythonLLM[LLM Client Stub]
    end

    subgraph Rust Microservices
        AnalystRs[Analyst Service (rayon, DashMap)]
        OrchRs[Orchestrator Core (tokio)]
        LLMRs[LLM Gateway (axum, hyper)]
    end

    subgraph Synapse (Knowledge Graph)
        KG[Semantic Engine]
    end

    PythonOrch -->|gRPC| OrchRs
    Agent -->|gRPC| PythonOrch
    Agent -->|gRPC / HTTP| LLMRs

    AnalystRs -->|gRPC / SPARQL| KG
    OrchRs -->|gRPC / SPARQL| KG
    LLMRs -->|gRPC / SPARQL| KG
```

### 2.1. Analyst Service (`analyst-service`)
*   **Responsabilidad:** Consumo asíncrono de eventos de fallo y clustering de alta velocidad.
*   **Tecnologías Clave:** `rayon` para paralelismo de datos (clustering masivo), `DashMap` para estructuras concurrentes, y `serde_json` para parsing eficiente.
*   **Integración gRPC:** Expondrá métodos para ingestar fallos y consultar/generar "Golden Rules" bajo demanda.

### 2.2. Orchestrator Core (`orchestrator-core`)
*   **Responsabilidad:** Máquina de estados principal, ruteo de tareas, y control concurrente (War Room / Council modes).
*   **Tecnologías Clave:** `tokio` (runtime asíncrono no bloqueante) y channels de alta concurrencia.
*   **Integración gRPC:** Expondrá `ExecuteSequence` y `ExecuteParallel`. El código Python en `sdk/python/agents/orchestrator.py` se reducirá a un simple cliente que delega la lógica pesada a Rust.

### 2.3. LLM Gateway (`llm-gateway`)
*   **Responsabilidad:** Proxy inverso de llamadas al LLM con validación de presupuesto en memoria (zero-latency).
*   **Tecnologías Clave:** `hyper`/`axum` para proxy HTTP/REST y gRPC. Caché de presupuesto LRU en memoria con flush asíncrono a Synapse.
*   **Integración:** Los agentes en Python apuntarán sus requests a la URL local de este proxy (ej. `http://localhost:50054/v1/chat/completions`).

## 3. Integración con el Orchestrator (gRPC)

Para integrar `orchestrator-core` con el sistema existente, se definirá el siguiente contrato `proto/orchestrator.proto`:

```protobuf
syntax = "proto3";

package orchestrator;

service OrchestratorService {
  rpc ExecuteTask (TaskRequest) returns (TaskResponse);
  rpc GetOperationalStatus (StatusRequest) returns (StatusResponse);
}

message TaskRequest {
  string description = 1;
  string target_stack = 2;
  string session_id = 3;
}

message TaskResponse {
  string final_status = 1;
  string error_message = 2;
  repeated string history_log = 3;
}
```

**Modificaciones a `sdk/python/agents/orchestrator.py`**:
*   Se eliminará el bucle `while` sincrónico y la lógica `time.sleep()`.
*   El método `run` instanciará un `grpc.insecure_channel` al puerto del nuevo servicio Rust.
*   Llamará al método `ExecuteTask` del stub gRPC generado.

## 4. Estrategia de Migración
1.  **Fase 1 (Dual Run):** Levantar los servicios Rust y rutear solo el 10% del tráfico de pruebas a ellos.
2.  **Fase 2 (Shadowing):** Validar la consistencia de estado contra las ejecuciones Python puras.
3.  **Fase 3 (Cutover):** Reemplazar las clases en Python con wrappers gRPC y depreciar el código Python antiguo.
