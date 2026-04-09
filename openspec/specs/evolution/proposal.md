# Propuesta OpenSpec: Migración a Microservicios en Rust

## 1. Resumen Ejecutivo
Basado en los registros (logs) de ejecución y la revisión de la arquitectura, la plataforma `agent-swarm-dev` está experimentando graves cuellos de botella computacionales y de I/O en Python. Esta propuesta detalla la migración de tres módulos críticos de Python—Analyst Agent, Orchestrator Core y LLM Service Gateway—a microservicios de Rust independientes y de alto rendimiento, integrados mediante gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y del bloqueo sincrónico, permitiendo así una concurrencia masiva y una latencia por debajo del milisegundo.

<!-- @synapse:rule: Evitar cuellos de botella de GIL y mejorar el rendimiento de concurrencia al migrar procesos bloqueantes a Rust -->

## 2. Cuellos de Botella Identificados (según Logs y Análisis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Gran carga computacional limitada por CPU durante la agrupación (clustering) de fallos y el reconocimiento de patrones.
- **Detalles**: Iterar a través de registros históricos extensos y ejecutar manipulaciones complejas de cadenas (Regex, parseo JSON) en Python escala de forma deficiente. El clustering sincrónico en memoria bloquea el event loop (bucle de eventos), causando graves picos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran importantes picos de CPU y retrasos en el procesamiento cuando se activa `cluster_failures` en grandes conjuntos de datos de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Cuellos de botella en la latencia de decisiones y en la gestión del estado.
- **Detalles**: El `autonomous_loop` principal se ve gravemente obstaculizado por operaciones I/O sincrónicas bloqueantes (como llamadas a bases de datos y solicitudes de API) y ciclos de `time.sleep`. El GIL de Python impide la verdadera ejecución en paralelo de agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y las trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando el sistema a manejar solo unas pocas tareas concurrentes de manera efectiva.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia limitada por I/O en la ruta crítica.
- **Detalles**: Interceptar cada llamada a los LLM para la aplicación del presupuesto (`check_budget`) desencadena consultas SPARQL sincrónicas a través de la red hacia Synapse. Esto añade una latencia masiva de tiempo de ida y vuelta (Round Trip Time, RTT) directamente al bucle de generación de IA.
- **Evidencia**: Los logs de ejecución indican que los decoradores inyectan más de 200 ms de sobrecarga por solicitud de inferencia, ralentizando drásticamente el razonamiento de múltiples pasos del agente.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un entorno de trabajo (Workspace) dedicado en Rust:

1. **`analyst-service` (Rust)**:
   - Implementar pipelines de procesamiento de datos concurrente utilizando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (por ejemplo, `DashMap`) para manejar el agrupamiento de logs y la generación de reglas de forma asíncrona.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estados autónoma utilizando el tiempo de ejecución (runtime) asíncrono `tokio`.
   - Desacoplar las transiciones de estado del I/O, permitiendo comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar una ventana deslizante (sliding window) en memoria o token bucket para el seguimiento del presupuesto, volcándolo al almacenamiento persistente de forma asíncrona sin bloquear la solicitud LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga inferior a un milisegundo para el LLM Gateway.
- **Rendimiento (Throughput)**: Incremento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando el multi-threading en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas de Python existentes (`tests/test_stack_routing.py`, etc.) pasan al ejecutarse contra los nuevos stubs de gRPC.
- Los servicios de Rust pueden ser instanciados de manera exitosa junto con la infraestructura existente mediante `start_all.sh`.
- Las evaluaciones comparativas empíricas (benchmarks) demuestran reducciones de latencia que se mapean con el Impacto Esperado.
