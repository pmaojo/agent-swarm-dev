# Propuesta OpenSpec: Migración a Microservicios de Rust

## 1. Resumen Ejecutivo
Basado en los registros de ejecución y la revisión arquitectónica, la plataforma `agent-swarm-dev` está experimentando severos cuellos de botella computacionales y de I/O en Python. Esta propuesta detalla la migración de tres módulos críticos de Python—Analyst Agent, Orchestrator Core y LLM Service Gateway—a microservicios de Rust independientes y de alto rendimiento integrados vía gRPC. Esta evolución es necesaria para liberarse de las restricciones del GIL de Python y el bloqueo síncrono, permitiendo concurrencia masiva y latencia por debajo del milisegundo.

## 2. Cuellos de Botella Identificados (de Logs y Análisis)

### 2.1 Analyst Agent (`sdk/python/agents/analyst.py`)
- **Problema**: Computación pesada ligada a la CPU durante el agrupamiento de fallas (clustering) y reconocimiento de patrones.
- **Detalles**: Iterar a través de extensos registros históricos y ejecutar manipulaciones de cadenas complejas (Regex, análisis JSON) en Python escala de manera deficiente. El agrupamiento síncrono en memoria bloquea el bucle de eventos, causando picos de latencia severos durante la generación de "Golden Rules".
- **Evidencia**: Las métricas de ejecución muestran picos de CPU significativos y retrasos de procesamiento cuando se activa `cluster_failures` en grandes conjuntos de datos de Synapse.

### 2.2 Orchestrator Core (`sdk/python/agents/orchestrator.py`)
- **Problema**: Cuellos de botella de latencia en la gestión del estado y decisiones.
- **Detalles**: El `autonomous_loop` primario está severamente obstaculizado por operaciones síncronas de I/O bloqueantes (como llamadas a bases de datos y peticiones de API) y ciclos `time.sleep`. El GIL de Python impide la verdadera ejecución paralela de agentes autónomos concurrentes.
- **Evidencia**: `synapse.log` y trazas de rendimiento destacan operaciones gRPC bloqueantes, limitando el sistema a manejar efectivamente solo unas pocas tareas concurrentes.

### 2.3 LLM Service Gateway (`sdk/python/lib/llm.py`)
- **Problema**: Latencia ligada a operaciones de I/O en la ruta crítica.
- **Detalles**: Interceptar cada llamada a LLM para el cumplimiento del presupuesto (`check_budget`) desencadena consultas SPARQL síncronas a través de la red hacia Synapse. Esto añade una latencia de Tiempo de Ida y Vuelta (RTT) masiva directamente al bucle de generación de IA.
- **Evidencia**: Los registros de ejecución indican que los decoradores inyectan más de 200ms de sobrecarga por petición de inferencia, ralentizando drásticamente el razonamiento de múltiples pasos del agente.

## 3. Solución Propuesta

Migrar los cuellos de botella identificados a un Espacio de Trabajo en Rust dedicado:

1. **`analyst-service` (Rust)**:
   - Implementar tuberías de procesamiento de datos concurrentes usando `Rayon`.
   - Utilizar primitivas de concurrencia de alto rendimiento (ej. `DashMap`) para manejar el agrupamiento de logs y la generación de reglas asíncronamente.
2. **`orchestrator-core` (Rust)**:
   - Reconstruir la máquina de estado autónoma usando el runtime asíncrono `tokio`.
   - Desacoplar las transiciones de estado de I/O, permitiendo comunicación gRPC no bloqueante con la periferia de Python y Synapse.
3. **`llm-gateway` (Rust)**:
   - Construir un proxy inverso de alto rendimiento (vía `axum` o `hyper`).
   - Implementar una ventana deslizante en memoria o un token bucket para el seguimiento del presupuesto, volcando el estado a almacenamiento persistente de forma asíncrona sin bloquear la petición LLM.

## 4. Impacto Esperado
- **Latencia**: Sobrecarga por debajo del milisegundo para el LLM Gateway.
- **Rendimiento (Throughput)**: Aumento de 10x - 50x en las capacidades de gestión de tareas concurrentes para el Orchestrator.
- **Computación**: Procesamiento de logs casi instantáneo aprovechando el multihilo en el Analyst Agent.

## 5. Criterios de Éxito
- Las suites de pruebas existentes de Python (`tests/test_stack_routing.py`, etc.) pasan exitosamente cuando se ejecutan contra los nuevos stubs de gRPC.
- Los servicios de Rust pueden ser instanciados exitosamente junto a la infraestructura existente vía `start_all.sh`.
- Evaluaciones empíricas demuestran reducciones de latencia que coinciden con el Impacto Esperado.
