<!-- @synapse:rule
Target: [Orchestrator gRPC Integration]
Inefficiency Detected: [Python GIL constraints, synchronous blocking I/O causing latency in agent task management and LLM tracking]
TDD Status: [Refactor]
Synapse Tag Injected: [Implement Strangler Fig pattern using Tonic/Tokio Rust backends connected to Python via asynchronous gRPC]
-->

# Diseño Técnico: Microservicios en Rust e Integración gRPC del Orquestador

## 1. Visión General de la Arquitectura

Tal como se describe en la Propuesta de Migración OpenSpec, los módulos de Python computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados por microservicios de Rust de alto rendimiento. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema de Python restante se comunicará con la nueva estructura principal (backbone) de Rust a través de gRPC.

### Diagrama del Sistema

```
[ Python Agents / CLI ]
        │
        ▼ (gRPC)
┌───────────────────────┐
│ llm-gateway (Rust)    │ ──► [ OpenAI / LiteLLM API ]
│ (Axum/Hyper proxy)    │
└────────┬──────────────┘
         │ (Async updates)
         ▼
[ Synapse Graph DB ] ◄─────┐
         ▲                 │
         │ (SPARQL/gRPC)   │ (gRPC)
┌────────┴──────────────┐  │
│ orchestrator-core     │  │
│ (Rust / Tokio)        │  │
└────────┬──────────────┘  │
         ▲                 │
         │ (gRPC streams)  │
┌────────┴──────────────┐  │
│ analyst-service       │──┘
│ (Rust / Rayon)        │
└───────────────────────┘
```

## 2. Estrategia de Integración gRPC

La migración utilizará un patrón "Strangler Fig". Definiremos interfaces Protobuf (`.proto`) para los métodos de clase de Python existentes, implementaremos los servidores en Rust (usando `tonic`) y cambiaremos las implementaciones de clase de Python para convertirlas en clientes gRPC (stubs).

### 2.1 Definiciones de Interfaz (`.proto`)

Se creará un `orchestration_engine.proto` unificado en el directorio `synapse-engine/crates/orchestration-engine/proto` (o una estructura similar).

**Ejemplo de Definiciones de Servicio:**

```protobuf
syntax = "proto3";
package orchestration;

// --- Analyst Service ---
service Analyst {
  rpc ClusterFailures (ClusterRequest) returns (ClusterResponse);
  rpc GenerateGoldenRules (RuleRequest) returns (RuleResponse);
}

// --- Orchestrator Core ---
service Orchestrator {
  rpc AssignTask (TaskRequest) returns (TaskResponse);
  rpc StreamStatus (TaskStatusRequest) returns (stream TaskStatusResponse);
}

// --- LLM Gateway ---
// Principalmente actúa como un proxy HTTP inverso, pero expone gestión vía gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC `tonic`. El núcleo del Orchestrator probablemente se vinculará al puerto `50054`, el Analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar las máquinas de estados de los agentes independientes. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar el análisis de logs dependiente de CPU sin bloquear el reactor asíncrono.

### 2.3 Stubs de Cliente Python (`grpcio`)

La base de código de Python se actualizará para usar los archivos `pb2` y `pb2_grpc` generados.

**Ejemplo de Actualización del Cliente Python (`sdk/python/agents/orchestrator.py`):**

```python
import grpc
from agents.synapse_proto import orchestration_pb2, orchestration_pb2_grpc

class OrchestratorAgent:
    def __init__(self, host='localhost:50054'):
        # Establecer conexión no bloqueante
        self.channel = grpc.insecure_channel(
            host,
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
        )
        # Intentar conexión, realizar respaldo (fallback) con gracia si Rust no está en ejecución
        try:
            grpc.channel_ready_future(self.channel).result(timeout=2.0)
            self.stub = orchestration_pb2_grpc.OrchestratorStub(self.channel)
        except grpc.FutureTimeoutError:
            self.stub = None
            print("WARNING: Rust Orchestrator unreachable, falling back to local Python logic.")

    def assign_task(self, task_data):
        if self.stub:
            req = orchestration_pb2.TaskRequest(data=task_data)
            return self.stub.AssignTask(req)
        else:
            # Respaldo (fallback) de Python legado
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de la Generación de Protobuf

Como se indica en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` a menudo tienen problemas con las importaciones relativas. Se debe incluir un script de compilación (build script) para parchear esto:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Parchear importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta (Roadmap) de Migración

1. **Fase 1: Definir Contratos:** Escribir archivos `.proto` basados en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop` y `LLMService.completion`.
2. **Fase 2: Andamiaje (Scaffolding) en Rust:** Inicializar workspaces de Cargo para los tres servicios e implementar respuestas gRPC simuladas (mock).
3. **Fase 3: Integración con Python:** Actualizar el SDK de Python para enrutar llamadas a través de los stubs (con respaldos (fallbacks) locales).
4. **Fase 4: Implementación en Rust:** Portar la lógica de negocio real (análisis Regex, máquinas de estados Tokio, enrutamiento Axum) a Rust.
5. **Fase 5: Transición (Cutover):** Eliminar los respaldos de Python una vez que se demuestre la estabilidad a través de pruebas de integración.