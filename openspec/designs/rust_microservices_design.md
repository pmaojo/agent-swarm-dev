# Diseño Técnico: CodeGraph Rust Microservices

**Autor:** SRE Team (Agent Jules)
**Fecha:** 2025-02-17
**Estado:** Draft

## 1. Visión General

Este documento detalla la arquitectura técnica para migrar los componentes críticos de `CodeGraph` (`CodeParser`, `CodeGraphIndexer`, `CodeGraphSlicer`) de Python a un microservicio de alto rendimiento en Rust (`codegraph-engine`). El objetivo es eliminar el overhead del GIL de Python y maximizar el uso de CPU multi-core para operaciones intensivas.

## 2. Arquitectura del Sistema

La nueva arquitectura introduce un servicio gRPC independiente que será consumido por el `Orchestrator` y otros agentes de Python.

```mermaid
graph TD
    subgraph Python SDK
        Orchestrator[Orchestrator Agent]
        IndexerPy[CodeGraphIndexer (Wrapper)]
        SlicerPy[CodeGraphSlicer (Wrapper)]
    end

    subgraph Rust Microservice (codegraph-engine)
        GRPC[gRPC Server (Tonic)]
        ParserRs[CodeParser (tree-sitter)]
        IndexerRs[Indexer Logic (rayon)]
        SlicerRs[Slicer Logic]
    end

    subgraph Synapse (Knowledge Graph)
        KG[Semantic Engine]
    end

    Orchestrator -->|Calls| IndexerPy
    IndexerPy -->|gRPC| GRPC
    SlicerPy -->|gRPC| GRPC
    IndexerRs -->|HTTP/SPARQL| KG
    SlicerRs -->|HTTP/SPARQL| KG
```

### 2.1 Comunicación

*   **Protocolo:** gRPC (Google Protocol Buffers v3).
*   **Transporte:** HTTP/2.
*   **Serialización:** Protobuf.

## 3. Definición del Servicio (gRPC)

El servicio `CodeGraphService` expondrá métodos para las operaciones principales. Ver `codegraph-engine/proto/codegraph.proto` para la definición exacta.

### Métodos Principales

1.  **`ParseFile(FileRequest) returns (ParseResponse)`**
    *   Recibe contenido de archivo o path.
    *   Retorna AST simplificado o lista de símbolos (Function, Class, Calls).
    *   Sustituye a `CodeParser.parse_file`.

2.  **`IndexRepository(IndexRequest) returns (stream IndexProgress)`**
    *   Recibe path del repositorio.
    *   Ejecuta `walk` en paralelo, parsea archivos, calcula hashes.
    *   Genera tripletas RDF y las envía a Synapse (directamente desde Rust o retornándolas a Python).
    *   **Decisión:** Rust enviará directamente a Synapse para evitar overhead de serialización hacia Python. Python solo recibe progreso/estado.

3.  **`SliceGraph(SliceRequest) returns (SliceResponse)`**
    *   Recibe `symbol_uri` y `depth`.
    *   Consulta Synapse (SPARQL) para obtener nodos relacionados.
    *   Lee archivos locales.
    *   Genera el "Skeleton Code" usando lógica de slicing optimizada en Rust.

## 4. Implementación en Rust

El proyecto se estructurará como un Workspace de Cargo:

```
codegraph-engine/
├── Cargo.toml (workspace)
├── proto/
│   └── codegraph.proto
├── codegraph-server/ (bin)
│   ├── main.rs (gRPC entrypoint)
│   └── service.rs (impl CodeGraphService)
├── codegraph-core/ (lib)
│   ├── parser.rs (tree-sitter wrapper)
│   ├── indexer.rs (parallel logic)
│   └── slicer.rs (graph/text logic)
└── codegraph-client/ (optional rust client)
```

### 4.1 Bibliotecas Clave

*   **Async Runtime:** `tokio`
*   **gRPC:** `tonic` (high performance, async)
*   **Protobuf:** `prost`
*   **Parsing:** `tree-sitter`, `tree-sitter-python`, `tree-sitter-rust`, etc.
*   **Parallelism:** `rayon` (para tareas CPU-bound síncronas si es necesario, o `tokio::spawn` para async IO).
*   **HTTP Client:** `reqwest` (para hablar con Synapse SPARQL endpoint).
*   **RDF:** `sophia` o `rio_turtle` (para generación eficiente de RDF).

## 5. Estrategia de Migración

1.  **Fase 1: Dual Stack**
    *   Desplegar `codegraph-engine` como sidecar o servicio independiente.
    *   Modificar `sdk/python/lib/code_parser.py` para intentar conectar gRPC primero, fallback a implementación local Python si falla.

2.  **Fase 2: Switchover**
    *   Hacer obligatorio el servicio Rust para entornos de producción/ci.
    *   Eliminar lógica pesada de Python, dejando solo los stubs gRPC.

## 6. Consideraciones de Seguridad

*   El servicio Rust tendrá acceso de lectura al sistema de archivos (repositorios).
*   Se debe validar que los paths solicitados estén dentro de los límites permitidos (sandbox).
*   Autenticación gRPC (mTLS o Token) si se despliega fuera de localhost.

## 7. Plan de Pruebas

*   **Unit Tests (Rust):** Pruebas exhaustivas de parsing y slicing.
*   **Integration Tests:** Levantar servicio Rust y Synapse mock, ejecutar suite de pruebas existente en Python (`test_code_parser_perf.py`) apuntando al nuevo servicio.
*   **Benchmark:** Comparar throughput (archivos/seg) entre Python puro y Rust impl.
