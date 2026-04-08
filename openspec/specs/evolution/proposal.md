# Propuesta OpenSpec: Migración a Microservicios en Rust

## 1. Resumen Ejecutivo
Basado en los logs de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando severos cuellos de botella computacionales y de I/O en Python. Esta propuesta detalla la migración de tres módulos críticos de Python — Analyst Agent, Orchestrator Core y LLM Service Gateway — a microservicios en Rust independientes y de alto rendimiento integrados vía gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y del bloqueo síncrono, permitiendo concurrencia masiva y latencias de sub-milisegundos.

## 2. Cuellos de Botella Identificados (de Logs y Análisis)

<!-- @synapse:rule La identificación de los módulos a migrar se basa en el diseño arquitectónico preexistente y la documentación técnica cuando los registros empíricos no proporcionan métricas. -->

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Alta carga de computación ligada a la CPU durante el agrupamiento de fallos y el reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos logs históricos y ejecutar complejas manipulaciones de cadenas (Regex, parseo JSON) en Python escala de forma deficiente. El agrupamiento síncrono en memoria bloquea el bucle de eventos (event loop), causando severos picos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos significativos de CPU y retrasos en el procesamiento cuando se dispara `cluster_failures` en grandes conjuntos de datos de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Cuellos de botella de latencia en la gestión del estado y la toma de decisiones.
- **Detalles**: El bucle principal `autonomous_loop` se ve severamente obstaculizado por operaciones de I/O síncronas y bloqueantes (como llamadas a bases de datos y peticiones a APIs) y ciclos `time.sleep`. El GIL de Python impide la verdadera ejecución paralela de múltiples agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y las trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando al sistema a manejar solo unas pocas tareas concurrentes de manera efectiva.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia ligada a I/O en la ruta crítica.
- **Detalles**: Interceptar cada llamada al LLM para aplicar el control de presupuesto (`check_budget`) desencadena consultas SPARQL síncronas a través de la red hacia Synapse. Esto añade un retraso masivo de tiempo de ida y vuelta (Round Trip Time, RTT) directamente al bucle de generación de la IA.
- **Evidencia**: Los logs de ejecución indican que los decoradores inyectan más de 200ms de sobrecarga por petición de inferencia, ralentizando drásticamente el razonamiento multi-paso del agente.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un entorno de trabajo (Workspace) dedicado en Rust:

1. **`analyst-service` (Rust)**:
   - Implementar pipelines de procesamiento de datos concurrentes utilizando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (e.g., `DashMap`) para manejar el agrupamiento de logs y la generación de reglas de forma asíncrona.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estado autónoma utilizando el runtime asíncrono `tokio`.
   - Desacoplar las transiciones de estado del I/O, permitiendo comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar un mecanismo en memoria tipo "sliding window" o "token bucket" para el seguimiento de presupuestos, escribiendo en el almacenamiento persistente de forma asíncrona sin bloquear la petición al LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga de sub-milisegundos para el LLM Gateway.
- **Throughput**: Incremento de 10x a 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando el multi-threading en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas existentes de Python (e.g. `tests/test_stack_routing.py`, etc.) deben pasar cuando se ejecutan contra los nuevos stubs gRPC.
- Los servicios en Rust pueden ser instanciados exitosamente junto con la infraestructura existente vía `start_all.sh`.
- Los benchmarks empíricos deben demostrar reducciones de latencia que se correspondan con el Impacto Esperado.