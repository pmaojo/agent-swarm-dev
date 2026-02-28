## Why

The current vector embedding paradigm suffers from "isotropy" (superposition), where information is smeared across all dimensions, forcing the system to process 1024d of noise just to determine a basic category. By implementing V5 Fractal Embeddings (scale-separated, hierarchical embeddings), we can break this superposition. This allows the system to use the first 64 dimensions as the "DNA of the Category," enabling a 3.7x faster query speed and a 75% reduction in initial compute cost by discarding 90% of irrelevant data in a first pass. This efficiency is critical for achieving "Soberanía del Laptop"—running massive, autonomous intelligence locally.

## What Changes

- Implement a Two-Stage Retrieval engine in Synapse (64d coarse filter + 256/1024d fine re-ranking).
- Update the Orchestrator agent to use 64d matching for lightning-fast, zero-LLM domain/intent routing.
- Tie the Godot "Fog of War" mechanic directly to vector resolution (distant/unexplored nodes only reveal their 64d coarse prefix, while explored nodes reveal the full high-res vector).
- Implement a local training pipeline/projection head over `fastembed` to align the Synapse RDF Ontology into the structural dimensions of the vectors.

## Capabilities

### New Capabilities

- `synapse-v5-search`: Two-stage vector retrieval engine using fractal dimension slicing.
- `orchestrator-fast-routing`: Zero-LLM agent routing based on 64d semantic prefixes.
- `fog-of-war-resolution`: Mechanism to selectively reveal vector dimensions based on exploration state.

### Modified Capabilities

<!-- No existing capabilities are being modified at the spec level; this is a net new architectural enhancement. -->

## Impact

- **synapse-engine:** Core retrieval logic, similarity functions, and data structures.
- **swarmd (Gateway):** API contracts and PyO3 bindings for embedding generation/slicing.
- **Orchestrator Agent:** Routing logic and task assignment flow.
- **Visualizer / Fog of War:** UI rendering based on partial vs. full knowledge resolution.
