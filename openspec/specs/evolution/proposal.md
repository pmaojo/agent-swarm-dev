# Propuesta de Migración a Microservicios de Rust

## 1. Resumen Ejecutivo
Tras el análisis de rendimiento de los logs de ejecución y la revisión del código fuente del sistema `agent-swarm-dev`, se han identificado tres módulos críticos que presentan cuellos de botella computacionales y de latencia significativos. Esta propuesta sugiere la migración de estos componentes de Python a microservicios independientes implementados en Rust, integrados mediante gRPC.

## 2. Análisis de Problemas (Cuellos de Botella)

### 2.1. Analyst Agent (`agents/analyst.py`)
- **Problema:** Procesamiento intensivo de CPU.
- **Detalle:** El método `cluster_failures` itera sobre grandes volúmenes de logs de fallos recuperados de Synapse. La manipulación de cadenas (regex, limpieza de JSON) y el agrupamiento en memoria en Python es ineficiente a medida que escala el histórico de ejecuciones.
- **Impacto:** Latencia alta en la generación de "Golden Rules", retrasando el aprendizaje del sistema.
- **Evidencia:** Iteración sincrónica sobre listas de resultados SPARQL y parsing JSON repetitivo.

### 2.2. Orchestrator Core (`agents/orchestrator.py`)
- **Problema:** Gestión de estado y latencia de decisión.
- **Detalle:** El bucle principal (`autonomous_loop`) depende de `time.sleep` y llamadas bloqueantes a Synapse y Trello. La lógica de transición de estados y verificación de guardrails (NIST) se ejecuta secuencialmente.
- **Impacto:** El Orchestrator no puede manejar miles de tareas concurrentes debido al GIL de Python y la falta de un modelo de eventos asíncrono real.
- **Evidencia:** Uso extensivo de llamadas bloqueantes gRPC dentro del bucle principal.

### 2.3. LLM Service Gateway (`lib/llm.py`)
- **Problema:** Latencia en la ruta crítica (I/O Bound).
- **Detalle:** Cada llamada al LLM invoca `check_budget`, lo que dispara una consulta SPARQL de agregación (`SUM`) a Synapse. Esto añade una latencia de red significativa (RTJ) a cada interacción con la IA.
- **Impacto:** Aumento del tiempo total de respuesta de los agentes y sobrecarga en Synapse por consultas de lectura frecuentes.
- **Evidencia:** Decoradores de presupuesto que bloquean la ejecución antes de cada `completion`.

## 3. Solución Propuesta

Migrar estos tres componentes a un arquitectura de microservicios en Rust (`workspace` de Cargo):

1.  **`analyst-service`**: Servicio de fondo que consume flujos de eventos de fallo y utiliza estructuras de datos eficientes (e.g., `DashMap`, Rayon) para clustering paralelo y generación de reglas.
2.  **`orchestrator-core`**: Máquina de estados de alto rendimiento basada en `tokio`. Manejará la lógica de transición y validación de reglas en memoria, sincronizándose asíncronamente con Synapse.
3.  **`llm-gateway`**: Proxy inverso de alta velocidad (basado en `axum` o `hyper`) que intercepta llamadas a OpenAI. Gestionará el presupuesto en memoria (con persistencia asíncrona) y el logging de tokens sin bloquear la respuesta.

## 4. Beneficios Esperados
- **Rendimiento:** Reducción del 90% en tiempo de procesamiento de logs (Analyst).
- **Latencia:** Reducción de ~200ms a <10ms en overhead por llamada al LLM (Gateway).
- **Escalabilidad:** Capacidad para manejar miles de agentes concurrentes sin bloqueo (Orchestrator).
- **Seguridad:** Tipado fuerte y manejo de memoria seguro con Rust.

## 5. Criterios de Éxito
- El sistema pasa todos los tests de integración existentes (`tests/test_stack_routing.py`).
- Los microservicios se comunican correctamente vía gRPC con los agentes restantes en Python.
- Reducción medible en el tiempo de ciclo de "Task Creation" a "Task Completion".
