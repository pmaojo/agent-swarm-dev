<!-- @synapse:rule Target: [Migration Design], Inefficiency Detected: [Python GIL constraints, synchronous I/O, and CPU-bound overhead causing severe latency], TDD Status: [Refactor], Synapse Tag Injected: [Diseño técnico traducido al español manteniendo todos los detalles de integración gRPC] -->
# Diseño Técnico: Microservicios en Rust e Integración gRPC del Orchestrator

## 1. Descripción General de la Arquitectura

Como se describe en la Propuesta de Migración OpenSpec, los módulos de Python que son computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados por microservicios de alto rendimiento en Rust. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema restante de Python se comunicará con la nueva columna vertebral de Rust a través de gRPC.

### Diagrama del Sistema

```
[ Agentes de Python / CLI ]
        │
        ▼ (gRPC)
┌───────────────────────┐
│ llm-gateway (Rust)    │ ──► [ OpenAI / LiteLLM API ]
│ (proxy Axum/Hyper)    │
└────────┬──────────────┘
         │ (Actualizaciones asíncronas)
         ▼
[ Base de Datos de Grafos Synapse ] ◄─────┐
         ▲                                │
         │ (SPARQL/gRPC)                  │ (gRPC)
┌────────┴──────────────┐                 │
│ orchestrator-core     │                 │
│ (Rust / Tokio)        │                 │
└────────┬──────────────┘                 │
         ▲                                │
         │ (flujos gRPC / streams)        │
┌────────┴──────────────┐                 │
│ analyst-service       │─────────────────┘
│ (Rust / Rayon)        │
└───────────────────────┘
```

## 2. Estrategia de Integración gRPC

La migración utilizará un patrón "Strangler Fig". Definiremos interfaces Protobuf (`.proto`) para los métodos de clase existentes en Python, implementaremos los servidores en Rust (usando `tonic`) y cambiaremos las implementaciones de clase de Python para que se conviertan en clientes gRPC (stubs).

### 2.1 Definiciones de Interfaz (`.proto`)

Se creará un `orchestration_engine.proto` unificado en el directorio `synapse-engine/crates/orchestration-engine/proto` (o estructura similar).

**Ejemplo de Definiciones de Servicio:**

```protobuf
syntax = "proto3";
package orchestration;

// --- Servicio Analyst ---
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
// Actúa principalmente como un proxy HTTP inverso, pero expone administración a través de gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC `tonic`. El Orchestrator core probablemente se vinculará al puerto `50054`, Analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar las máquinas de estado de agentes independientes. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar el análisis de registros limitado por CPU sin estancar el reactor asíncrono.

### 2.3 Stubs de Cliente en Python (`grpcio`)

La base de código de Python se actualizará para usar los archivos `pb2` y `pb2_grpc` generados.

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
        # Intentar conexión, con alternativa gracefully si Rust no se está ejecutando
        try:
            grpc.channel_ready_future(self.channel).result(timeout=2.0)
            self.stub = orchestration_pb2_grpc.OrchestratorStub(self.channel)
        except grpc.FutureTimeoutError:
            self.stub = None
            print("ADVERTENCIA: Orchestrator en Rust inalcanzable, recurriendo a la lógica local de Python.")

    def assign_task(self, task_data):
        if self.stub:
            req = orchestration_pb2.TaskRequest(data=task_data)
            return self.stub.AssignTask(req)
        else:
            # Lógica alternativa de Python legacy
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de la Generación de Protobuf

Como se señala en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` a menudo tienen problemas de importación relativa. Se debe incluir un script de compilación para parchear estos:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Parchear importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta (Roadmap) de Migración

1. **Fase 1: Definir Contratos:** Escribir archivos `.proto` basados en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop` y `LLMService.completion`.
2. **Fase 2: Estructuración en Rust:** Inicializar espacios de trabajo (workspaces) de Cargo para los tres servicios e implementar respuestas gRPC de prueba (mocks).
3. **Fase 3: Integración de Python:** Actualizar el SDK de Python para enrutar las llamadas a través de los stubs (con alternativas locales).
4. **Fase 4: Implementación en Rust:** Portar la lógica de negocio real (parseo Regex, máquinas de estado de Tokio, enrutamiento Axum) a Rust.
5. **Fase 5: Transición (Cutover):** Eliminar las alternativas de Python una vez que la estabilidad se demuestre a través de pruebas de integración.