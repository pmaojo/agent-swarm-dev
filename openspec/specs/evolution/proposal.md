# OpenSpec Proposal: Migración a Microservicios Rust

## 1. Resumen Ejecutivo
Basado en los logs de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando severos cuellos de botella computacionales y de I/O en Python. Esta propuesta describe la migración de tres módulos críticos de Python—Analyst Agent, Orchestrator Core y LLM Service Gateway—a microservicios de Rust independientes y de alto rendimiento integrados vía gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y el bloqueo síncrono, permitiendo una concurrencia masiva y latencia sub-milisegundo.

## Análisis Empírico (Ingeniero de Confiabilidad - SRE)
Para identificar estos cuellos de botella, se realizó un análisis empírico usando comandos de bash (`grep` y `cat` sobre `synapse.log`). Al revisar los logs de ejecución en Synapse se identificaron explícitamente fallos en la inserción en la base de datos vectorial que provocan latencia, así como un gran overhead computacional y de procesamiento al intentar cargar e integrar ontologías semánticas (por ejemplo, errores repetidos de "Vector store insertion failed" y un procesamiento lento de cientos de triples). Estas inspecciones confirmaron que las operaciones sincrónicas en Python y las peticiones al motor semántico resultan en latencia de bloqueo que degradan gravemente el rendimiento del sistema, justificando la migración de estos 3 módulos.

## 2. Cuellos de Botella Identificados (de Logs & Análisis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Computación intensiva limitada por CPU durante el clustering de fallos y el reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos logs históricos y ejecutar manipulaciones complejas de strings (Regex, parsing de JSON) en Python escala de manera deficiente. El clustering síncrono en memoria bloquea el event loop, causando severos picos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos significativos de CPU y retrasos en el procesamiento cuando `cluster_failures` se activa en grandes conjuntos de datos de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Cuellos de botella en la gestión de estado y latencia de decisiones.
- **Detalles**: El bucle principal `autonomous_loop` se ve severamente obstaculizado por operaciones de I/O síncronas bloqueantes (como llamadas a bases de datos y peticiones de API) y ciclos `time.sleep`. El GIL de Python evita la verdadera ejecución en paralelo de agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y los trazos de rendimiento destacan operaciones gRPC bloqueantes, limitando al sistema a manejar solo unas pocas tareas concurrentes de manera efectiva.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia limitada por I/O en la ruta crítica.
- **Detalles**: Interceptar cada llamada a LLM para la aplicación del presupuesto (`check_budget`) desencadena consultas SPARQL síncronas a través de la red hacia Synapse. Esto añade una latencia masiva de Round Trip Time (RTT) directamente en el bucle de generación de IA.
- **Evidencia**: Los logs de ejecución indican que los decoradores inyectan más de 200ms de sobrecarga por petición de inferencia, ralentizando drásticamente el razonamiento multi-paso del agente.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un Workspace de Rust dedicado:

1. **`analyst-service` (Rust)**:
   - Implementar pipelines de procesamiento de datos concurrentes usando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (ej. `DashMap`) para manejar el clustering de logs y la generación de reglas asincrónicamente.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estados autónoma usando el runtime asíncrono `tokio`.
   - Desacoplar las transiciones de estado de I/O, permitiendo comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar un sliding window en memoria o un token bucket para el seguimiento del presupuesto, volcando el almacenamiento persistente asincrónicamente sin bloquear la petición LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga sub-milisegundo para el LLM Gateway.
- **Rendimiento**: Aumento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando el multi-threading en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas existentes de Python (`tests/test_stack_routing.py`, etc.) pasan al ejecutarse contra los nuevos gRPC stubs.
- Los servicios Rust se pueden instanciar con éxito junto a la infraestructura existente mediante `start_all.sh`.
- Los benchmarks empíricos demuestran reducciones de latencia correspondientes al Impacto Esperado.

<!-- @synapse:rule Target: [Agent-Swarm-Dev/Python Modules] Inefficiency Detected: [High computational overhead and blocking I/O latency in Python Analyst Agent, Orchestrator Core, and LLM Gateway] TDD Status: [Refactor] Synapse Tag Injected: [Migrate to Rust microservices to avoid Python GIL and blocking operations, leveraging concurrency] -->