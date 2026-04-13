# Diseño Técnico: Microservicios Rust e Integración gRPC con el Orchestrator

## 1. Visión General de la Arquitectura

Como se describe en la Propuesta de Migración OpenSpec, los módulos de Python computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados con microservicios de Rust de alto rendimiento. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema de Python restante se comunicará con el nuevo backend de Rust vía gRPC.

### Diagrama del Sistema

```
[ Python Agents / CLI ]
        │
        ▼ (gRPC)
┌───────────────────────┐
│ llm-gateway (Rust)    │ ──► [ OpenAI / LiteLLM API ]
│ (Axum/Hyper proxy)    │
└────────┬──────────────┘
         │ (Actualizaciones asíncronas)
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

La migración utilizará un patrón "Strangler Fig". Definiremos interfaces Protobuf (`.proto`) para los métodos de las clases Python existentes, implementaremos los servidores en Rust (usando `tonic`), e intercambiaremos las implementaciones de las clases Python para que se conviertan en clientes gRPC (stubs).

### 2.1 Definiciones de Interfaz (`.proto`)

Se creará un `orchestration_engine.proto` unificado en el directorio `synapse-engine/crates/orchestration-engine/proto` (o estructura similar).

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
// Principalmente actúa como un proxy HTTP inverso, pero expone administración vía gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC con `tonic`. El núcleo del Orchestrator probablemente se vinculará al puerto `50054`, el Analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar máquinas de estado de agentes independientes. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar el análisis de logs limitado por CPU sin detener el reactor asíncrono.

### 2.3 Stubs de Clientes de Python (`grpcio`)

La base de código de Python se actualizará para usar los archivos generados `pb2` y `pb2_grpc`.

**Ejemplo de Actualización de Cliente Python (`sdk/python/agents/orchestrator.py`):**

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
        # Intentar conexión, con fallback elegante si Rust no se está ejecutando
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
            # Fallback a la lógica heredada de Python
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de la Generación de Protobuf

Como se señala en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` suelen tener problemas de importación relativa. Se debe incluir un script de construcción para parchearlos:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Parchear importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta de Migración

1. **Fase 1: Definir Contratos:** Escribir archivos `.proto` basados en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop` y `LLMService.completion`.
2. **Fase 2: Andamiaje de Rust:** Inicializar workspaces de Cargo para los tres servicios e implementar respuestas gRPC de prueba (mocks).
3. **Fase 3: Integración con Python:** Actualizar el SDK de Python para rutear las llamadas a través de los stubs (con fallbacks locales).
4. **Fase 4: Implementación en Rust:** Portar la lógica de negocio real (análisis Regex, máquinas de estado de Tokio, enrutamiento de Axum) a Rust.
5. **Fase 5: Cambio Definitivo:** Eliminar los fallbacks de Python una vez que se demuestre la estabilidad a través de pruebas de integración.

<!-- @synapse:rule Target: [Agent-Swarm-Dev/Python-Rust Integration] Inefficiency Detected: [gRPC code generation mapping and absolute imports breaking in Python 3] TDD Status: [Refactor] Synapse Tag Injected: [Ensure fallback logic to standard Python when gRPC fails, and use absolute to relative import patching (`from . import`) for protobufs] -->