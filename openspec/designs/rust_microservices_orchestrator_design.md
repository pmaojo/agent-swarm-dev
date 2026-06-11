# Diseño Técnico: Microservicios en Rust e Integración gRPC del Orchestrator

## 1. Visión General de la Arquitectura

Como se describe en la Propuesta de Migración OpenSpec, los módulos de Python computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados por microservicios de alto rendimiento en Rust. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema de Python restante se comunicará con la nueva columna vertebral de Rust a través de gRPC.

### Diagrama del Sistema

```
[ Agentes de Python / CLI ]
        │
        ▼ (gRPC)
┌───────────────────────┐
│ llm-gateway (Rust)    │ ──► [ OpenAI / API LiteLLM ]
│ (Proxy Axum/Hyper)    │
└────────┬──────────────┘
         │ (Actualizaciones asíncronas)
         ▼
[ Grafo DB Synapse ] ◄─────┐
         ▲                 │
         │ (SPARQL/gRPC)   │ (gRPC)
┌────────┴──────────────┐  │
│ orchestrator-core     │  │
│ (Rust / Tokio)        │  │
└────────┬──────────────┘  │
         ▲                 │
         │ (Streams gRPC)  │
┌────────┴──────────────┐  │
│ analyst-service       │──┘
│ (Rust / Rayon)        │
└───────────────────────┘
```

## 2. Estrategia de Integración gRPC

La migración utilizará un patrón "Strangler Fig". Definiremos interfaces Protobuf (`.proto`) para los métodos de clases de Python existentes, implementaremos los servidores en Rust (usando `tonic`), e intercambiaremos las implementaciones de las clases de Python para que se conviertan en clientes gRPC (stubs).

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
// Actúa principalmente como proxy HTTP inverso, pero expone gestión vía gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC `tonic`. El núcleo del orchestrator probablemente se vinculará al `50054`, el analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar máquinas de estado de agentes independientes. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar análisis de logs vinculados a la CPU sin detener el reactor asíncrono.

### 2.3 Stubs de Clientes Python (`grpcio`)

El código fuente en Python será actualizado para utilizar los archivos generados `pb2` y `pb2_grpc`.

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
        # Intentar conexión, fallback de forma elegante si Rust no está corriendo
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
            # Fallback a Python heredado
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de Generación Protobuf

Como se señala en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` a menudo tienen problemas de importación relativa. Se debe incluir un script de compilación para parchearlos:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Parchear importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta de Migración

1. **Fase 1: Definir Contratos:** Escribir archivos `.proto` basados en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop` y `LLMService.completion`.
2. **Fase 2: Andamiaje en Rust:** Inicializar los workspaces de Cargo para los tres servicios e implementar respuestas gRPC mockeadas.
3. **Fase 3: Integración con Python:** Actualizar el SDK de Python para enrutar llamadas a través de los stubs (con fallbacks locales).
4. **Fase 4: Implementación en Rust:** Portar la lógica de negocio real (análisis Regex, máquinas de estado Tokio, enrutamiento Axum) a Rust.
5. **Fase 5: Corte Final:** Eliminar los fallbacks de Python una vez probada la estabilidad a través de pruebas de integración.