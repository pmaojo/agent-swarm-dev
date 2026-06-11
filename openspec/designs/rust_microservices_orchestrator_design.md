# Diseño Técnico: Microservicios en Rust e Integración gRPC del Orchestrator

## 1. Visión General de la Arquitectura

Tal como se describe en la Propuesta de Migración de OpenSpec, los módulos de Python computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados por microservicios de alto rendimiento en Rust. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema de Python restante se comunicará con la nueva columna vertebral de Rust a través de gRPC.

<!-- @synapse:rule: Implementar el patrón "Strangler Fig" con fallbacks locales en Python para asegurar la resiliencia durante la migración a gRPC -->

### Diagrama del Sistema

```
[ Agentes de Python / CLI ]
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
         │ (Streams gRPC)  │
┌────────┴──────────────┐  │
│ analyst-service       │──┘
│ (Rust / Rayon)        │
└───────────────────────┘
```

## 2. Estrategia de Integración gRPC

La migración utilizará un patrón "Strangler Fig". Definiremos interfaces Protobuf (`.proto`) para los métodos de clases de Python existentes, implementaremos los servidores en Rust (usando `tonic`), e intercambiaremos las implementaciones de las clases de Python para que se conviertan en clientes gRPC (stubs).

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
// Actúa principalmente como proxy inverso HTTP, pero expone administración vía gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC `tonic`. Probablemente, el Orchestrator core se enlazará al puerto `50054`, Analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar las máquinas de estado de los agentes de forma independiente. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar análisis de logs intensivos en CPU sin detener el reactor asíncrono.

### 2.3 Stubs del Cliente Python (`grpcio`)

El código base de Python se actualizará para usar los archivos generados `pb2` y `pb2_grpc`.

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
        # Intentar conexión, fallback de manera segura si Rust no está en ejecución
        try:
            grpc.channel_ready_future(self.channel).result(timeout=2.0)
            self.stub = orchestration_pb2_grpc.OrchestratorStub(self.channel)
        except grpc.FutureTimeoutError:
            self.stub = None
            print("WARNING: Rust Orchestrator inalcanzable, usando la lógica local de Python de reserva.")

    def assign_task(self, task_data):
        if self.stub:
            req = orchestration_pb2.TaskRequest(data=task_data)
            return self.stub.AssignTask(req)
        else:
            # Fallback a la lógica de Python heredada
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de la Generación Protobuf

Como se indica en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` a menudo tienen problemas de importación relativa. Se debe incluir un script de compilación para parchearlos:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Parchear importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta de Migración

1. **Fase 1: Definir Contratos:** Escribir archivos `.proto` basados en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop` y `LLMService.completion`.
2. **Fase 2: Scaffolding en Rust:** Inicializar los entornos de trabajo Cargo para los tres servicios e implementar respuestas gRPC simuladas (mock).
3. **Fase 3: Integración con Python:** Actualizar el SDK de Python para enrutar las llamadas a través de los stubs (con fallbacks locales).
4. **Fase 4: Implementación en Rust:** Migrar la lógica de negocio real (parseo Regex, máquinas de estado de Tokio, enrutamiento Axum) a Rust.
5. **Fase 5: Transición (Cutover):** Eliminar los fallbacks de Python una vez que la estabilidad sea comprobada mediante pruebas de integración.
