# Diseño Técnico: Microservicios en Rust para Orchestrator, Analyst y LLM Gateway

## Objetivo
Convertir los módulos de Python computacionalmente pesados (Analyst Agent, Orchestrator Core, LLM Service Gateway) en microservicios independientes en Rust que interactúen a través de gRPC, eliminando el overhead del GIL de Python y mejorando significativamente la latencia y la concurrencia.

## Arquitectura

### 1. Definiciones Protobuf
Los nuevos servicios se definirán en un nuevo paquete, por ejemplo, `orchestrator.v1`.

```protobuf
syntax = "proto3";
package orchestrator.v1;

service OrchestratorService {
  rpc RouteTask(RouteTaskRequest) returns (RouteTaskResponse);
  rpc ManageStateGraph(StateGraphRequest) returns (StateGraphResponse);
}

service AnalystService {
  rpc OptimizePrompt(OptimizePromptRequest) returns (OptimizePromptResponse);
  rpc ClusterFailures(ClusterFailuresRequest) returns (ClusterFailuresResponse);
}

service LlmGatewayService {
  rpc Complete(LlmCompletionRequest) returns (LlmCompletionResponse);
}
```

### 2. Implementación en Rust (`orchestrator-engine` / `synapse-engine`)
- Utilizar `tonic` y `tokio` para la publicación asíncrona de los servicios gRPC.
- Integrar `fastembed-rs` (si está disponible, o equivalentes en Rust) para las matemáticas de vectores de alta dimensión (Fractal Search V5).
- Implementar caché LRU en memoria para el `LlmGatewayService`.
- Desplegar como binarios independientes o como un servicio backend unificado dentro del ecosistema de Synapse.

### 3. Integración en Python (`sdk/python/agents/orchestrator.py`, etc.)
- Emplear `grpc_tools.protoc` para generar los archivos `orchestrator_pb2.py` y `orchestrator_pb2_grpc.py`.
- Instanciar stubs gRPC dentro de las clases de agentes, de manera similar a la integración existente con el `CodeGraphService`.
- Reemplazar la lógica interna pesada de Python con llamadas a los stubs hacia el servidor Rust. Proporcionar verificaciones de canal asíncronas y no bloqueantes (ej., `grpc.channel_ready_future`) para mitigar fallos temporales de conexión, o hacer fallback elegantemente.

## Integración gRPC con el Orchestrator

Para conectar el ecosistema de agentes Python con los nuevos microservicios, se implementará un cliente gRPC dentro de la clase `OrchestratorAgent`.

1. **Importación de Protobufs**:
   Se importarán los archivos generados (e.g., `orchestrator_pb2_grpc`) asegurando un correcto empaquetado y utilizando las rutas relativas adecuadas en Python 3 para los archivos `_grpc.py`.

2. **Inicialización**:
   Se añadirán variables de entorno (como `ORCHESTRATOR_GRPC_HOST` y `ORCHESTRATOR_GRPC_PORT`) para inicializar los canales gRPC dinámicamente.

3. **Ciclo de Vida de la Conexión**:
   Se implementarán métodos de conexión (`connect`) e inicialización segura del `OrchestratorServiceStub`, con una gestión adecuada para cerrar el canal al finalizar.

## Impacto
- Reducción sustancial en el tiempo de CPU durante tareas de alta concurrencia ("War Room").
- Mejora de latencia en la ruta crítica (colapso de tokens del Analyst, enrutamiento LLM).
- Desacoplamiento de la lógica base de Python para preparar una modernización más amplia del backend.