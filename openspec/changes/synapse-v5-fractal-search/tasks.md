## 1. Vector Engine Core (Rust)

- [ ] 1.1 Implement `VectorUtils::fractal_similarity` in `synapse-engine` to compute sub-slice dot products.
- [ ] 1.2 Modify `SemanticEngine::search_similar` to accept a `prefix_only` boolean flag.
- [ ] 1.3 Create `search_two_stage` pipeline: filter top N candidates using 64d, then re-rank top M using full dimensionality.
- [ ] 1.4 Update gRPC / REST contracts in Synapse to expose the two-stage search capabilities.

## 2. Gateway Integration (Python/Rust)

- [ ] 2.1 Update `swarmd` embedding API to support prefix slicing requests.
- [ ] 2.2 Add NumPy/PyTorch projection head loading logic in the fastembed worker.
- [ ] 2.3 Modify the `Memory` agent to execute two-stage SPARQL/Vector queries against Synapse.

## 3. Orchestration & UI

- [ ] 3.1 Refactor `Orchestrator` to generate a 64d task vector and calculate cosine similarity against agent profiles instead of using LLM classification.
- [ ] 3.2 Add 64d capability prefixes to the `swarm_schema.yaml` or agent definitions.
- [ ] 3.3 Update Godot UI state / TUI to obscure distant nodes beyond the 64d prefix, simulating the hierarchical Fog of War.
- [ ] 3.4 Benchmarking: Add telemetry event for `vector_search_latency` to verify the 3.7x speedup.
