# Diseño Técnico: Migración a Microservicios Rust

## 1. Arquitectura del Sistema

El sistema evolucionará de un monolito modular en Python a una arquitectura híbrida donde el núcleo de alto rendimiento reside en Rust, mientras que los agentes de lógica de negocio (Coder, Reviewer, Product Manager) permanecen en Python por flexibilidad.

### Diagrama de Componentes

```mermaid
graph TD
    User[User / Trello] -->|HTTP| Bridge[Trello Bridge (Python)]
    Bridge -->|gRPC| Orch[Orchestrator Core (Rust)]

    subgraph Rust High-Performance Zone
        Orch -->|gRPC| Analyst[Analyst Service (Rust)]
        Orch -->|gRPC| LLM[LLM Gateway (Rust)]
        Analyst -->|gRPC| Synapse[Synapse Engine (Rust)]
        LLM -->|gRPC| Synapse
    end

    subgraph Python Agent Zone
        Orch -->|gRPC| Coder[Coder Agent]
        Orch -->|gRPC| Reviewer[Reviewer Agent]
        Coder -->|HTTP| LLM
        Reviewer -->|HTTP| LLM
    end
```

## 2. Estructura del Workspace (Cargo)

Se utilizará un único workspace de Cargo para gestionar las dependencias compartidas.

```toml
# Cargo.toml (root)
[workspace]
members = [
    "analyst-service",
    "orchestrator-core",
    "llm-gateway",
    "shared-types"
]

[workspace.dependencies]
tokio = { version = "1", features = ["full"] }
tonic = "0.10"
prost = "0.12"
serde = { version = "1", features = ["derive"] }
reqwest = { version = "0.11", features = ["json"] }
synapse-client = { path = "../synapse-engine/client" } # Si aplica
```

### 2.1. Analyst Service (`analyst-service`)
- **Responsabilidad:** Procesamiento masivo de logs y generación de "Golden Rules".
- **Tecnologías:** `rayon` (paralelismo de datos), `regex` (optimizado), `dashmap` (concurrencia).
- **Entrada:** Flujo de eventos de fallo (gRPC Stream o Polling a Synapse).
- **Salida:** Ingesta de `HardConstraint` en Synapse.

### 2.2. Orchestrator Core (`orchestrator-core`)
- **Responsabilidad:** Máquina de estados central, gestión de tareas y verificación de cumplimiento (NIST).
- **Tecnologías:** `tokio` (Async I/O), `tonic` (gRPC Server), `petgraph` (si se requiere lógica de grafo compleja en memoria).
- **Lógica:** Implementará el bucle de decisión sin bloqueo, manteniendo el estado de miles de tareas en memoria y persistiendo solo los cambios de estado en Synapse.

### 2.3. LLM Gateway (`llm-gateway`)
- **Responsabilidad:** Proxy inverso para OpenAI/Anthropic, control de presupuesto y logging.
- **Tecnologías:** `axum` (Web Server), `tower` (Middleware), `leaky-bucket-lite` (Rate Limiting).
- **Lógica:**
    - Intercepta `/v1/chat/completions`.
    - Verifica presupuesto en caché local (sincronizada asíncronamente con Synapse cada N segundos).
    - Loguea uso de tokens en una cola asíncrona para no bloquear la respuesta.

## 3. Interfaces gRPC (.proto)

### 3.1. Orchestrator Interface (`orchestrator.proto`)

```protobuf
syntax = "proto3";
package orchestrator;

service Orchestrator {
  // Registro de agentes Python
  rpc RegisterAgent (AgentInfo) returns (RegisterResponse);

  // Asignación de tareas (Long Polling o Stream)
  rpc PollTask (AgentQuery) returns (TaskAssignment);

  // Reporte de resultados
  rpc SubmitResult (TaskResult) returns (Ack);
}

message AgentInfo {
  string name = 1;
  repeated string capabilities = 2; // e.g. ["python", "react"]
}

message TaskAssignment {
  string task_id = 1;
  string description = 2;
  string context = 3;
  repeated string constraints = 4; // Golden Rules
}

message TaskResult {
  string task_id = 1;
  string status = 2; // "success", "failure"
  string artifact = 3;
  string error_message = 4;
}
```

### 3.2. Analyst Interface (`analyst.proto`)

```protobuf
syntax = "proto3";
package analyst;

service Analyst {
  // Ingesta directa de fallos (bypass de Synapse para análisis inmediato)
  rpc ReportFailure (FailureEvent) returns (AnalysisResult);

  // Consulta de reglas consolidadas
  rpc GetGoldenRules (RuleQuery) returns (RuleList);
}

message FailureEvent {
  string agent_id = 1;
  string task_id = 2;
  string error_log = 3;
  string stack = 4;
}

message AnalysisResult {
  bool rule_generated = 1;
  string rule_content = 2;
}
```

### 3.3. LLM Gateway Interface (`llm_gateway.proto`)

El Gateway actuará principalmente como un proxy HTTP compatible con OpenAI, pero expondrá gRPC para administración.

```protobuf
syntax = "proto3";
package llm_gateway;

service BudgetControl {
  rpc GetCurrentSpend (Empty) returns (SpendReport);
  rpc ResetBudget (Empty) returns (Ack);
  rpc SetLimit (LimitConfig) returns (Ack);
}

message SpendReport {
  double current_spend = 1;
  double limit = 2;
  double remaining = 3;
}
```

## 4. Plan de Implementación

1.  **Fase 1: Andamiaje.** Crear el workspace de Rust y los proyectos base. Configurar la compilación de protos.
2.  **Fase 2: LLM Gateway.** Implementar el proxy básico. Reemplazar la URL base en los agentes Python (`lib/llm.py`) para apuntar al servicio Rust local.
3.  **Fase 3: Analyst Service.** Migrar la lógica de clustering. Modificar `agents/analyst.py` para que sea un cliente gRPC delgado o eliminarlo por completo si el servicio Rust se auto-ejecuta.
4.  **Fase 4: Orchestrator Core.** Migrar la máquina de estados. Mantener `agents/orchestrator.py` temporalmente como adaptador para los agentes legados, delegando la lógica al núcleo Rust.

## 5. Consideraciones de Despliegue

- Los servicios Rust se compilarán como binarios estáticos (`musl`) para facilitar el despliegue en contenedores Docker "scratch" o "distroless".
- Se expondrán métricas Prometheus en `/metrics` para monitoreo de latencia y throughput.
