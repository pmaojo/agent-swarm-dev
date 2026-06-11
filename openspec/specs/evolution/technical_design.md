# Diseño Técnico: Migración a Microservicios Rust (Orchestration Engine)

## 1. Arquitectura General
El `orchestration-engine` es un nuevo crate basado en Rust (`synapse-engine/crates/orchestration-engine`) que sustituirá a la lógica nativa en Python de tres componentes clave para eliminar los cuellos de botella y reducir la latencia general del sistema:
- **Analyst Agent (`analyst-service`)**
- **Orchestrator Core (`orchestrator-core`)**
- **LLM Service Gateway (`llm-gateway`)**

Estos microservicios independientes se integran en el clúster a través del patrón **Strangler Fig**, exponiendo endpoints gRPC que los clientes Python consumen como fallback/proxy si los servicios están disponibles.

## 2. Microservicios y Puertos (gRPC)
Cada componente lógico corre sobre su propio puerto aislado usando `tonic` y `tokio` para asegurar la no-interferencia y maximizar el rendimiento de red.

- **Orchestrator Service:** `localhost:50054`
- **Analyst Service:** `localhost:50055`
- **LLM Gateway Service:** `localhost:50056`

## 3. Integración gRPC con el Orchestrator de Python
Los clientes en Python instancian canales (`grpc.insecure_channel`) hacia estos puertos e intentan invocar la lógica de Rust. El archivo protobuf central para esta integración es `orchestration_engine.proto` (ubicado en `synapse-engine/crates/orchestration-engine/proto/orchestration_engine.proto`).

Para regenerar los bindings en el entorno de Python:
```bash
python -m grpc_tools.protoc -I synapse-engine/crates/orchestration-engine/proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto synapse-engine/crates/orchestration-engine/proto/orchestration_engine.proto
```

### 3.1. Analyst Service (`50055`)
Se migrará el método intensivo en CPU `cluster_failures` y `optimize_prompt`. Rust manejará el parseo y agrupamiento de los logs en paralelo usando `Rayon` o estructuras concurrentes `DashMap`, retornando los clusters a Python en milisegundos.

### 3.2. Orchestrator Core (`50054`)
Se transfiere la responsabilidad de la máquina de estados y las transiciones de `autonomous_loop`. `tokio` permitirá mantener miles de conexiones activas simultáneas, evaluando reglas de guardrails sin bloquear I/O.

### 3.3. LLM Gateway (`50056`)
Servirá como un proxy de muy baja latencia. El cálculo y validación asíncrona de presupuestos se hace fuera de la ruta crítica de la llamada LLM, reduciendo significativamente la latencia inyectada (previamente >200ms) a <10ms.

## 4. Estándar IEA y TDD
<!-- @synapse:rule Target: [orchestration-engine/gRPC Integration] Inefficiency Detected: [Python GIL bloquea la concurrencia y añade overhead significativo de I/O a las operaciones críticas del Orchestrator (Analyst, Loop, LLM Gateway).] TDD Status: [Red/Green/Refactor] Synapse Tag Injected: [Implementar llamadas gRPC asíncronas no bloqueantes en Python y microservicios Rust con tokio/tonic para la ruta crítica.] -->

## 5. Próximos Pasos de Implementación
1. Implementar los servidores `tonic` en Rust.
2. Añadir asserts de rendimiento a las pruebas TDD del `analyst.py` y `llm.py` en Python para validar la reducción de latencia (Red Phase).
3. Conectar el cliente Python (`orchestrator.py`, `llm.py`, `analyst.py`) usando el `orchestration_engine_pb2_grpc` generado (Green Phase).
4. Refactorizar y limpiar el código delegado de Python (Refactor).