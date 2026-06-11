# Propuesta OpenSpec: Migración a Microservicios en Rust

## 1. Resumen Ejecutivo
Basado en los logs de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando cuellos de botella computacionales y de E/S (I/O) severos en Python. Esta propuesta detalla la migración de tres módulos críticos de Python—Analyst Agent, Orchestrator Core y LLM Service Gateway—a microservicios de Rust independientes y de alto rendimiento integrados vía gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y el bloqueo síncrono, habilitando concurrencia masiva y latencia de submilisegundos.

## 2. Cuellos de Botella Identificados (de Logs y Análisis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Gran carga computacional vinculada a la CPU durante el agrupamiento (clustering) de fallos y reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos logs históricos y ejecutar manipulaciones complejas de strings (Regex, parsing de JSON) en Python escala de manera deficiente. El clustering síncrono en memoria bloquea el bucle de eventos (event loop), causando picos severos de latencia durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos significativos de CPU y retrasos en el procesamiento cuando se activa `cluster_failures` en grandes conjuntos de datos de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Gestión del estado y cuellos de botella en la latencia de decisiones.
- **Detalles**: El `autonomous_loop` primario está severamente obstaculizado por operaciones de E/S síncronas que bloquean (como llamadas a bases de datos y peticiones a APIs) y ciclos `time.sleep`. El GIL de Python impide la verdadera ejecución paralela de agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando al sistema a manejar eficazmente solo unas pocas tareas concurrentes.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia vinculada a la E/S en la ruta crítica.
- **Detalles**: Interceptar cada llamada a los LLM para la aplicación del presupuesto (`check_budget`) desencadena consultas SPARQL síncronas sobre la red a Synapse. Esto añade una latencia masiva de Round Trip Time (RTT) directamente al bucle de generación de IA.
- **Evidencia**: Los logs de ejecución indican que los decoradores inyectan más de 200ms de sobrecarga por petición de inferencia, ralentizando drásticamente el razonamiento de los agentes en múltiples pasos.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un Workspace dedicado de Rust:

1. **`analyst-service` (Rust)**:
   - Implementar pipelines de procesamiento de datos concurrentes usando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (por ejemplo, `DashMap`) para manejar el clustering de logs y generación de reglas asíncronamente.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estado autónoma usando el runtime asíncrono `tokio`.
   - Desacoplar las transiciones de estado de la E/S, permitiendo comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar una ventana deslizante en memoria o token bucket para el seguimiento del presupuesto, volcando al almacenamiento persistente asíncronamente sin bloquear la petición LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga de submilisegundos para el LLM Gateway.
- **Rendimiento (Throughput)**: Aumento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando multithreading en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas en Python existentes (`tests/test_stack_routing.py`, etc.) pasan al ejecutarse contra los nuevos stubs gRPC.
- Los servicios de Rust pueden ser instanciados exitosamente junto a la infraestructura existente vía `start_all.sh`.
- Las pruebas de rendimiento empíricas demuestran reducciones de latencia que se corresponden con el Impacto Esperado.