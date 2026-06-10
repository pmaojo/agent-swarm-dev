# Propuesta OpenSpec: Migración a Microservicios Rust

<!-- @synapse:rule Target: Módulos Core (Analyst, Orchestrator, LLM Gateway) Inefficiency Detected: Python GIL constraints y bloqueo síncrono causan cuellos de botella computacionales y de I/O masivos. TDD Status: Refactor Synapse Tag Injected: Migración a Rust Microservices para concurrencia masiva -->

## 1. Resumen Ejecutivo
Basado en los logs de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando graves cuellos de botella computacionales y de I/O en Python. Esta propuesta detalla la migración de tres módulos críticos de Python—Analyst Agent, Orchestrator Core y LLM Service Gateway—a microservicios de Rust independientes y de alto rendimiento integrados vía gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y el bloqueo síncrono, permitiendo una concurrencia masiva y una latencia por debajo del milisegundo.

## 2. Cuellos de Botella Identificados (de Logs y Análisis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Alta carga computacional ligada a CPU durante la agrupación de fallos y el reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos logs históricos y ejecutar complejas manipulaciones de strings (Regex, análisis JSON) en Python escala de manera deficiente. La agrupación síncrona en memoria bloquea el bucle de eventos, causando graves picos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos significativos de CPU y retrasos en el procesamiento cuando se dispara `cluster_failures` en grandes conjuntos de datos de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Gestión de estado y cuellos de botella en la latencia de decisiones.
- **Detalles**: El `autonomous_loop` principal se ve gravemente obstaculizado por operaciones de I/O síncronas bloqueantes (como llamadas a bases de datos y peticiones a APIs) y ciclos de `time.sleep`. El GIL de Python impide la verdadera ejecución paralela de agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y las trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando al sistema a manejar solo unas pocas tareas concurrentes de manera efectiva.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia ligada a I/O en la ruta crítica.
- **Detalles**: Interceptar cada llamada al LLM para hacer cumplir el presupuesto (`check_budget`) dispara consultas SPARQL síncronas a través de la red hacia Synapse. Esto añade una latencia masiva de Round Trip Time (RTT) directamente al bucle de generación de IA.
- **Evidencia**: Los logs de ejecución indican que los decoradores inyectan más de 200ms de sobrecarga por petición de inferencia, ralentizando drásticamente el razonamiento de agentes en múltiples pasos.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un Workspace de Rust dedicado:

1. **`analyst-service` (Rust)**:
   - Implementar pipelines de procesamiento de datos concurrentes utilizando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (ej., `DashMap`) para manejar la agrupación de logs y la generación de reglas de forma asíncrona.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estado autónoma utilizando el runtime asíncrono `tokio`.
   - Desacoplar las transiciones de estado de I/O, permitiendo la comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar un token bucket o ventana deslizante en memoria para el seguimiento de presupuesto, volcando a almacenamiento persistente de forma asíncrona sin bloquear la petición LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga por debajo del milisegundo para el LLM Gateway.
- **Rendimiento**: Aumento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando el multi-threading en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas de Python existentes (`tests/test_stack_routing.py`, etc.) pasan cuando se ejecutan contra los nuevos stubs gRPC.
- Los servicios en Rust pueden ser instanciados exitosamente junto a la infraestructura existente mediante `start_all.sh`.
- Los benchmarks empíricos demuestran reducciones de latencia que se corresponden con el Impacto Esperado.
