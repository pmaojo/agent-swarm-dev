<!-- @synapse:rule
Target: [Analyst, Orchestrator, LLM Gateway]
Inefficiency Detected: [Python GIL constraints, synchronous blocking I/O, regex overhead causing latency and computation bottlenecks in Python modules]
TDD Status: [Refactor]
Synapse Tag Injected: [Migrate to Rust independent microservices for concurrent and high performance system execution via gRPC]
-->

# Propuesta OpenSpec: Migración a Microservicios en Rust

## 1. Resumen Ejecutivo
Basado en los logs de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando graves cuellos de botella computacionales y de E/S en Python. Esta propuesta detalla la migración de tres módulos críticos de Python —Agente Analista (Analyst Agent), Núcleo del Orquestador (Orchestrator Core) y Puerta de Enlace del Servicio LLM (LLM Service Gateway)— a microservicios independientes de alto rendimiento en Rust, integrados vía gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y el bloqueo síncrono, permitiendo una concurrencia masiva y una latencia por debajo del milisegundo.

## 2. Cuellos de Botella Identificados (de Logs & Análisis)

### 2.1 Agente Analista (`sdk/python/agents/analyst.py`)
- **Problema**: Gran carga computacional dependiente de la CPU durante la agrupación de fallos y el reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos logs históricos y ejecutar manipulaciones complejas de cadenas (Regex, análisis JSON) en Python no escala bien. La agrupación en memoria síncrona bloquea el bucle de eventos, causando graves picos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos significativos de CPU y retrasos de procesamiento cuando se activa `cluster_failures` en conjuntos de datos grandes de Synapse.

### 2.2 Núcleo del Orquestador (`sdk/python/agents/orchestrator.py`)
- **Problema**: Cuellos de botella en la latencia de decisiones y gestión del estado.
- **Detalles**: El `autonomous_loop` principal se ve gravemente obstaculizado por operaciones de E/S síncronas bloqueantes (como llamadas a bases de datos y peticiones a APIs) y ciclos `time.sleep`. El GIL de Python impide una verdadera ejecución paralela de los agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y las trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando al sistema a manejar eficazmente solo unas pocas tareas concurrentes.

### 2.3 Puerta de Enlace del Servicio LLM (`sdk/python/lib/llm.py`)
- **Problema**: Latencia vinculada a la E/S en la ruta crítica.
- **Detalles**: Interceptar cada llamada al LLM para la aplicación del presupuesto (`check_budget`) desencadena consultas SPARQL síncronas a través de la red hacia Synapse. Esto añade una latencia masiva de tiempo de ida y vuelta (Round Trip Time o RTT) directamente al bucle de generación de IA.
- **Evidencia**: Los logs de ejecución indican que los decoradores inyectan más de 200 ms de sobrecarga por petición de inferencia, ralentizando drásticamente el razonamiento del agente de múltiples pasos.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un Espacio de Trabajo (Workspace) dedicado en Rust:

1. **`analyst-service` (Rust)**:
   - Implementar pipelines de procesamiento de datos concurrentes utilizando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (por ejemplo, `DashMap`) para manejar la agrupación de logs y la generación de reglas de forma asíncrona.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estados autónoma utilizando el tiempo de ejecución asíncrono `tokio`.
   - Desacoplar las transiciones de estado de la E/S, permitiendo una comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar una ventana deslizante en memoria o un sistema "token bucket" para el seguimiento del presupuesto, volcando al almacenamiento persistente de forma asíncrona sin bloquear la petición LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga por debajo del milisegundo para la Puerta de Enlace LLM (LLM Gateway).
- **Rendimiento (Throughput)**: Aumento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orquestador.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando el multihilo en el Agente Analista (Analyst Agent).

## 5. Criterios de Éxito
- Las suites de pruebas en Python existentes (`tests/test_stack_routing.py`, etc.) pasan cuando se ejecutan contra los nuevos stubs de gRPC.
- Los servicios de Rust pueden ser instanciados exitosamente junto con la infraestructura existente vía `start_all.sh`.
- Las evaluaciones empíricas (benchmarks) demuestran reducciones de latencia correspondientes con el Impacto Esperado.