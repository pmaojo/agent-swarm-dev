# Propuesta OpenSpec: Migración a Microservicios de Rust

## 1. Motivación y Resumen Ejecutivo
Tras el análisis de los logs de ejecución en Synapse (`synapse.log`) y los cuellos de botella del sistema, se ha identificado que tres módulos críticos de Python presentan altos niveles de carga computacional y latencia, principalmente debido a las limitaciones del GIL de Python y el procesamiento sincrónico:
1. **Analyst Agent** (`sdk/python/agents/analyst.py`): Realiza un procesamiento de texto intensivo, clustering y optimización de prompts, lo cual consume ciclos de CPU considerables.
2. **Orchestrator Core** (`sdk/python/agents/orchestrator.py`): Manejo complejo de máquinas de estado, procesamiento del grafo de ejecución en paralelo, y enrutamiento "Zero-LLM" mediante matemática de vectores de alta dimensionalidad (Fractal Search V5).
3. **LLM Service Gateway** (`sdk/python/lib/cloud_gateways/factory.py` / `sdk/python/lib/llm.py`): Gestión del caché de LLM, peticiones a APIs externas y lógica de fallback que generan latencia de I/O bloqueante.

## 2. Propuesta de Arquitectura

Se propone migrar estos tres módulos a microservicios independientes implementados en Rust, integrados en el ecosistema existente mediante llamadas a procedimientos remotos (gRPC), de manera similar a como opera actualmente `codegraph-engine`.

## 3. Beneficios Esperados

* **Concurrencia y Rendimiento:** La adopción del runtime asíncrono de Rust (como `tokio`) permitirá una gestión paralela más eficiente sin los bloqueos introducidos por el GIL de Python, especialmente en tareas del Orchestrator.
* **Reducción de Latencia:** Las computaciones matemáticas intensivas para búsqueda de similitud de vectores y el clustering de datos en el Analyst Agent operarán a una fracción del tiempo de respuesta actual.
* **Confiabilidad del Sistema:** Un sistema de tipos fuertes como el de Rust minimizará la superficie de errores en tiempo de ejecución.

## 4. Estrategia de Migración

1. Definir los contratos de los servicios mediante `Protobuf` (`.proto`).
2. Implementar los servidores gRPC en Rust utilizando `tonic`.
3. Generar las interfaces de comunicación (bindings gRPC) para Python mediante `grpcio-tools`.
4. Refactorizar los agentes y librerías actuales en Python para actuar como clientes gRPC y comunicarse asíncronamente con los nuevos microservicios en Rust.