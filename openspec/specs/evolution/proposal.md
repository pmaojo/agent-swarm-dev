<!-- @synapse:rule Target: [OpenSpec Proposal], Inefficiency Detected: [Python GIL constraints, synchronous I/O, and CPU-bound overhead causing severe latency], TDD Status: [Refactor], Synapse Tag Injected: [Documentación arquitectónica actualizada al español manteniendo rigor técnico] -->
# Propuesta OpenSpec: Migración a Microservicios en Rust

## 1. Resumen Ejecutivo
Con base en los registros de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando graves cuellos de botella computacionales y de E/S en Python. Esta propuesta describe la migración de tres módulos críticos de Python —Analyst Agent, Orchestrator Core y LLM Service Gateway— a microservicios independientes de alto rendimiento en Rust, integrados a través de gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y el bloqueo síncrono, permitiendo concurrencia masiva y latencia sub-milisegundo.

## 2. Cuellos de Botella Identificados (de Registros y Análisis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Computación pesada dependiente de la CPU durante la agrupación de fallos y el reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos registros históricos y ejecutar manipulaciones complejas de cadenas (Regex, parseo de JSON) en Python escala de forma deficiente. La agrupación síncrona en memoria bloquea el bucle de eventos, causando graves picos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos significativos de CPU y retrasos en el procesamiento cuando se activa `cluster_failures` en conjuntos de datos grandes de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Gestión de estado y cuellos de botella en la latencia de decisiones.
- **Detalles**: El bucle principal `autonomous_loop` se ve gravemente obstaculizado por operaciones de E/S síncronas que bloquean (como llamadas a bases de datos y solicitudes a API) y ciclos `time.sleep`. El GIL de Python impide la verdadera ejecución en paralelo de agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando el sistema a manejar solo unas pocas tareas concurrentes de manera efectiva.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia dependiente de la E/S en la ruta crítica.
- **Detalles**: Interceptar cada llamada a LLM para la aplicación del presupuesto (`check_budget`) desencadena consultas SPARQL síncronas a través de la red hacia Synapse. Esto añade una enorme latencia Round Trip Time (RTT) directamente al bucle de generación de IA.
- **Evidencia**: Los registros de ejecución indican que los decoradores inyectan más de 200 ms de sobrecarga por solicitud de inferencia, ralentizando drásticamente el razonamiento del agente de múltiples pasos.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un Espacio de Trabajo dedicado en Rust:

1. **`analyst-service` (Rust)**:
   - Implementar canalizaciones de procesamiento de datos concurrentes utilizando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (por ejemplo, `DashMap`) para manejar la agrupación de registros y la generación de reglas de forma asíncrona.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estado autónoma utilizando el entorno de ejecución asíncrono `tokio`.
   - Desacoplar las transiciones de estado de la E/S, permitiendo la comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar una ventana deslizante en memoria o un token bucket para el seguimiento del presupuesto, volcando a almacenamiento persistente de forma asíncrona sin bloquear la solicitud de LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga sub-milisegundo para el LLM Gateway.
- **Rendimiento (Throughput)**: Aumento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de registros casi instantáneo aprovechando el multi-hilo en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas existentes de Python (`tests/test_stack_routing.py`, etc.) pasan exitosamente cuando se ejecutan contra los nuevos stubs gRPC.
- Los servicios en Rust se pueden instanciar con éxito junto con la infraestructura existente mediante `start_all.sh`.
- Las evaluaciones empíricas (benchmarks) demuestran reducciones de latencia que concuerdan con el Impacto Esperado.