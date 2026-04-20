# OpenSpec Proposal: Migración de Componentes Python a Microservicios Rust (Analyst, Orchestrator, LLM Gateway)

**Autor:** SRE Team (Agent Jules)
**Fecha:** 2025-02-17
**Estado:** Pendiente de Aprobación

## Resumen Ejecutivo

Esta propuesta recomienda la migración de los tres módulos de Python con mayor carga computacional y latencia a microservicios independientes implementados en Rust, los cuales se comunicarán a través de gRPC. El objetivo principal es eliminar los cuellos de botella generados por el Global Interpreter Lock (GIL) de Python y las operaciones I/O síncronas que afectan significativamente el rendimiento y la escalabilidad del sistema.

## Análisis SRE y Cuellos de Botella Identificados

Basado en el análisis de los logs de ejecución en Synapse (`synapse.log`) y el código fuente, se identificaron los siguientes módulos críticos:

1. **Analyst Agent (`sdk/python/agents/analyst.py`)**
   - **Problema:** Alta carga de procesamiento de texto, optimización de prompts y algoritmos de clustering. Operaciones limitadas por el rendimiento monohilo de Python.
   - **Impacto:** Latencia severa al manipular grandes volúmenes de tokens y cadenas de texto repetitivas, degradando la agilidad analítica de todo el enjambre.

2. **Orchestrator Core (`sdk/python/agents/orchestrator.py`)**
   - **Problema:** Gestión compleja de la máquina de estados, procesamiento del grafo de ejecución en paralelo ("War Room") y operaciones matemáticas avanzadas como el enrutamiento vectorial (Fractal Search V5 con vectores de 64d) usando cálculos de similitud de coseno.
   - **Impacto:** Imposibilidad de manejar miles de agentes/tareas concurrentes. El GIL de Python bloquea el paralelismo real de tareas, limitando la escalabilidad "Zero-LLM" prevista para las consultas SPARQL/vectoriales masivas.

3. **LLM Service Gateway (`sdk/python/lib/cloud_gateways/factory.py` / `sdk/python/lib/llm.py`)**
   - **Problema:** Gestión de llamadas a APIs externas de LLMs (incluyendo latencias de red), lógica de failover/fallback, y validaciones constantes de presupuesto (`check_budget` a través de SPARQL).
   - **Impacto:** Las verificaciones secuenciales y el bloqueo I/O por cada llamada introducen latencia innecesaria (~200ms adicionales), penalizando drásticamente la latencia promedio del ecosistema de agentes.

## Solución Propuesta

Migrar la lógica crítica de estos tres módulos a nuevos microservicios en Rust (`analyst-service`, `orchestrator-core`, y `llm-gateway`), dentro del ecosistema `synapse-engine` existente o un workspace dedicado.

### Puntos Clave del Diseño
* **Servidores gRPC:** Utilizando `tonic` y `tokio` para la ejecución asíncrona real de todas las llamadas de red y CPU.
* **Integración Python:** Los agentes de Python actuales se convertirán en "clientes ligeros" o *stubs* gRPC que delegarán las operaciones pesadas a los microservicios en Rust.
* **Vector Math (Orchestrator):** Operaciones nativas en Rust (y potencialmente delegadas al propio semantic-engine) para el cálculo de similitud vectorial a velocidades exponencialmente más rápidas que `numpy` de Python o rutinas equivalentes.
* **Caching (LLM Gateway):** Implementación LRU de bajo nivel (Thread-safe) en Rust que servirá las peticiones de los distintos workers Python sin bloqueos.

## Beneficios Esperados

1. **Latencia Extremadamente Baja:** Eliminación total de bloqueos asíncronos en capa Python; procesamiento casi instantáneo (reducción de >90%) de texto de prompts.
2. **Concurrencia sin Restricciones (Escalabilidad):** Tokio/Rust permitirá gestionar decenas de miles de tareas sin sufrir los impactos del GIL, habilitando arquitecturas distribuidas de alta densidad ("Soberanía del Laptop").
3. **Consistencia:** Rust garantizará menores errores de tiempo de ejecución (Out of Memory, Data Races) durante escenarios de alto estrés y picos de tráfico.

## Conclusión

Se requiere la **aprobación humana** para proceder. Si la propuesta es aprobada, el siguiente paso será desarrollar la arquitectura y diseño técnico (ArchOps) de la interfaz gRPC y la integración completa con el Orchestrator.
