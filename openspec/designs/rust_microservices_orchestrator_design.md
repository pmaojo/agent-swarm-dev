# Diseño Técnico: Microservicios en Rust e Integración gRPC con el Orchestrator

<!-- @synapse:constraint Los microservicios deben usar puertos independientes y utilizar el patrón Strangler Fig (fallback a la lógica en Python) al integrarse con los clientes Python, para evitar interrupciones masivas en la disponibilidad de los agentes durante la migración. -->

## 1. Visión General de la Arquitectura

Tal y como se delinea en la Propuesta de Migración OpenSpec, los módulos de Python computacionalmente pesados y sensibles a la latencia (Analyst, Orchestrator Core, LLM Gateway) serán reemplazados con microservicios de alto rendimiento en Rust. Este documento de diseño especifica la capa de integración, centrándose en cómo el ecosistema de Python restante se comunicará con el nuevo backend en Rust a través de gRPC.

### Diagrama del Sistema

```
[ Agentes Python / CLI ]
        │
        ▼ (gRPC)
┌───────────────────────┐
│ llm-gateway (Rust)    │ ──► [ OpenAI / API LiteLLM ]
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
         │ (Flujos gRPC / Streams)        │
┌────────┴──────────────┐                 │
│ analyst-service       │─────────────────┘
│ (Rust / Rayon)        │
└───────────────────────┘
```

## 2. Estrategia de Integración gRPC

La migración utilizará un patrón "Strangler Fig". Definiremos interfaces Protobuf (`.proto`) para los métodos existentes de las clases en Python, implementaremos los servidores en Rust (utilizando `tonic`), y modificaremos las implementaciones de las clases en Python para que se conviertan en clientes gRPC (stubs).

### 2.1 Definiciones de Interfaces (`.proto`)

Se creará un archivo unificado `orchestration_engine.proto` en el directorio `synapse-engine/crates/orchestration-engine/proto` (o estructura similar).

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
// Principalmente actúa como un proxy inverso HTTP, pero expone gestión vía gRPC
service LLMManager {
  rpc CheckBudget (BudgetRequest) returns (BudgetResponse);
  rpc UpdateQuotas (QuotaRequest) returns (QuotaResponse);
}
```

### 2.2 Implementación en Rust (`tonic` & `tokio`)

- **Configuración del Servidor:** Cada microservicio ejecutará un servidor gRPC `tonic`. Es probable que el núcleo del Orchestrator se vincule al puerto `50054`, el Analyst al `50055`, etc.
- **Concurrencia:** El `orchestrator-core` utilizará `tokio::spawn` para gestionar las máquinas de estado independientes de los agentes. El `analyst-service` usará `rayon` dentro de hilos bloqueantes de Tokio para realizar el análisis de logs vinculado a la CPU sin estancar el reactor asíncrono.

### 2.3 Stubs de Clientes en Python (`grpcio`)

El código base en Python se actualizará para usar los archivos generados `pb2` y `pb2_grpc`.

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
        # Intentar conexión, fallback de forma elegante si Rust no está ejecutándose
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
            # Fallback a la lógica local de Python (Legacy)
            return self._legacy_assign_task(task_data)
```

## 3. Manejo de la Generación de Protobuf

Tal y como se indica en la memoria del sistema, los archivos `_grpc.py` de Python generados por `protoc` suelen tener problemas con importaciones relativas. Se debe incluir un script de compilación para parchearlos:

```bash
# Generar
python -m grpc_tools.protoc -I proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto proto/orchestration_engine.proto

# Parchear importaciones
sed -i 's/import orchestration_engine_pb2/from . import orchestration_engine_pb2/g' sdk/python/agents/synapse_proto/orchestration_engine_pb2_grpc.py
```

## 4. Hoja de Ruta de Migración (Roadmap)

1. **Fase 1: Definir Contratos:** Escribir los archivos `.proto` basados en los esquemas de entrada/salida de `AnalystAgent.cluster_failures`, `OrchestratorAgent.autonomous_loop`, y `LLMService.completion`.
2. **Fase 2: Andamiaje (Scaffolding) en Rust:** Inicializar los workspaces de Cargo para los tres servicios e implementar respuestas gRPC simuladas (mocks).
3. **Fase 3: Integración con Python:** Actualizar el SDK de Python para enrutar las llamadas a través de los stubs (con fallbacks locales).
4. **Fase 4: Implementación en Rust:** Portar la lógica de negocio real (parseo Regex, máquinas de estado de Tokio, enrutamiento con Axum) a Rust.
5. **Fase 5: Cambio Definitivo (Cutover):** Eliminar los fallbacks de Python una vez que la estabilidad se haya probado mediante tests de integración.