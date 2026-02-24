# Propuesta OpenSpec: Migración de Componentes CodeGraph a Rust Microservices

**Autor:** SRE Team (Agent Jules)
**Fecha:** 2025-02-17
**Estado:** Proposed

## Resumen Ejecutivo

Esta propuesta recomienda la migración de los módulos de Python `CodeParser`, `CodeGraphIndexer`, y `CodeGraphSlicer` a microservicios implementados en Rust. El objetivo es eliminar los cuellos de botella de rendimiento relacionados con el Global Interpreter Lock (GIL) de Python, la sobrecarga de bindings de `tree-sitter` en Python, y la ejecución secuencial de operaciones intensivas en I/O y CPU.

## Análisis de Cuellos de Botella

Tras realizar un análisis de rendimiento (SRE Audit) y simulación de carga, se identificaron los siguientes problemas críticos en la implementación actual de Python:

1.  **CodeParser (`sdk/python/lib/code_parser.py`)**
    -   **Métrica:** ~0.5ms por archivo pequeño (10-20 líneas).
    -   **Problema:** Aunque `tree-sitter` es rápido (C/C++), la capa de Python introduce overhead al cruzar la frontera del lenguaje repetidamente para recorrer el AST y generar diccionarios.
    -   **Escalabilidad:** Lineal con el tamaño del archivo y el número de archivos. Bloquea el hilo principal durante el parsing.

2.  **CodeGraphIndexer (`sdk/python/lib/code_graph_indexer.py`)**
    -   **Métrica:** Limitado por I/O secuencial y CPU (hashing).
    -   **Problema:** Utiliza `os.walk` que es síncrono y monohilo. El cálculo de hashes SHA256 y la generación de tripletas RDF compiten por el GIL, impidiendo el uso efectivo de múltiples núcleos.
    -   **Impacto:** Tiempos de indexación prohibitivos para repositorios grandes (>10k archivos).

3.  **CodeGraphSlicer (`sdk/python/lib/code_graph_slicer.py`)**
    -   **Métrica:** Alta latencia en manipulación de strings y recorridos de grafo.
    -   **Problema:** La lógica de "slicing" implica múltiples pasadas sobre el contenido del archivo y manipulación de strings en memoria, lo cual es ineficiente en Python comparado con Rust.
    -   **Dependencia:** Realiza llamadas gRPC bloqueantes a Synapse.

## Solución Propuesta: Arquitectura Microservicios Rust

Se propone reescribir estos componentes como un servicio gRPC unificado en Rust (`codegraph-engine`).

### Tecnologías Clave
*   **Lenguaje:** Rust (Edición 2021) - Seguridad de memoria sin Garbage Collector.
*   **gRPC:** `tonic` (Implementación gRPC de alto rendimiento sobre `hyper`).
*   **Parsing:** `tree-sitter` (Bindings nativos de Rust, zero-overhead).
*   **Paralelismo:** `rayon` para procesamiento de datos en paralelo (parsing, hashing).
*   **File System:** `jwalk` o `walkdir` para recorrido de sistema de archivos en paralelo.

### Beneficios Esperados
1.  **Rendimiento:** Reducción estimada del 90% en tiempos de indexación y parsing gracias al paralelismo real (sin GIL) y optimizaciones de bajo nivel.
2.  **Escalabilidad:** Capacidad para manejar repositorios masivos con huella de memoria constante.
3.  **Confiabilidad:** Sistema de tipos de Rust previene errores de tiempo de ejecución comunes (NullPointer, Data Races).

## Plan de Implementación

1.  Definición de contrato gRPC (`codegraph_service.proto`).
2.  Desarrollo del servicio Rust `codegraph-engine`.
3.  Creación de cliente Python (Adapter) en `sdk/python/lib/` para reemplazar la lógica actual con llamadas gRPC.
4.  Despliegue progresivo (Shadow Mode -> Live).

## Siguiente Paso

Si esta propuesta es aprobada, se procederá inmediatamente al diseño técnico detallado de la interfaz gRPC y la arquitectura de integración con el Orchestrator.
