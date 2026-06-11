# Diseño Técnico: Microservicios en Rust e Integración gRPC del Orchestrator

## 1. Visión General de la Arquitectura

Como se describe en la Propuesta de Migración de OpenSpec, los módulos de Python computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados por microservicios en Rust de alto rendimiento. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema restante de Python se comunicará con la nueva columna vertebral en Rust a través de gRPC.

### Diagrama del Sistema

```
[ Agentes de Python / CLI ]
        │
        ▼ (gRPC)
┌───────────────────────┐
│ llm-gateway (Rust)    │ ──► [ OpenAI / LiteLLM API ]
│ (Proxy Axum/Hyper)    │
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
         │ (Flujos gRPC)   │
┌────────┴──────────────┐  │
│ analyst-service       │──┘
│ (Rust / Rayon)        │
└───────────────────────┘
```

## 2. Estrategia de Integración gRPC

La migración utilizará el patrón "Strangler Fig" (Higuera Estranguladora). Definiremos interfaces Protobuf (`.proto`) para los métodos de clase de Python existentes, implementaremos los servidores en Rust (usando `tonic`), e intercambiaremos las implementaciones de clase en Python para convertirlas en clientes gRPC (stubs).

### 2.1 Definición de Interfaces (`.proto`)

Se creará un archivo unificado `orchestration_engine.proto` en el directorio `synapse-engine/crates/orchestration-engine/proto` (o estructura similar).

**Ejemplo de Definición de Servicios:**

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
// Actúa principalmente como proxy HTTP inverso, pero expone gestión vía gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC `tonic`. El núcleo del Orchestrator probablemente se vinculará al puerto `50054`, el Analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar máquinas de estado de agentes independientes. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar el análisis de registros ligado a la CPU sin estancar el reactor asíncrono.

### 2.3 Stubs de Clientes Python (`grpcio`)

La base de código de Python será actualizada para usar los archivos `pb2` y `pb2_grpc` generados.

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
        # Intentar conectar, recurrir localmente si Rust no está ejecutándose
        try:
            grpc.channel_ready_future(self.channel).result(timeout=2.0)
            self.stub = orchestration_pb2_grpc.OrchestratorStub(self.channel)
        except grpc.FutureTimeoutError:
            self.stub = None
            print("ADVERTENCIA: Orchestrator de Rust inalcanzable, recurriendo a lógica local de Python.")

    def assign_task(self, task_data):
        if self.stub:
            req = orchestration_pb2.TaskRequest(data=task_data)
            return self.stub.AssignTask(req)
        else:
            # Fallback a lógica legacy en Python
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de la Generación de Protobuf

Como se indica en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` a menudo tienen problemas con importaciones relativas. Se debe incluir un script de construcción para corregirlos:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Corregir importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta de Migración

1. **Fase 1: Definición de Contratos:** Escribir los archivos `.proto` basándose en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop` y `LLMService.completion`.
2. **Fase 2: Andamiaje (Scaffolding) en Rust:** Inicializar los espacios de trabajo (workspaces) de Cargo para los tres servicios e implementar respuestas gRPC de prueba (mock).
3. **Fase 3: Integración en Python:** Actualizar el SDK de Python para enrutar las llamadas a través de los stubs (con fallbacks locales).
4. **Fase 4: Implementación en Rust:** Portar la lógica de negocio real (análisis Regex, máquinas de estado de Tokio, enrutamiento Axum) a Rust.
5. **Fase 5: Transición (Cutover):** Eliminar los fallbacks de Python una vez que se demuestre la estabilidad a través de pruebas de integración.
