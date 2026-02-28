## Context

The current vector embedding architecture in Synapse uses a flat, 1024d/256d vector search algorithm. This "isotropy" (superposition) approach mixes coarse category information (e.g., Domain) with fine-grained details across the entire vector. Consequently, simple coarse queries require processing identical amounts of compute and memory as high-precision semantic queries. This design limits the scalability of running multiple independent agents on local consumer hardware (Soberanía del Laptop), as every graph query incurs a maximum computational penalty.

## Goals / Non-Goals

**Goals:**

- Implement V5 Fractal Embeddings logic where the first 64 dimensions reliably encode coarse category/domain information.
- Introduce a Two-Stage Retrieval pipeline in Synapse to filter 90% of candidates using only the 64d prefix before applying the full 256d/1024d search on the remainder.
- Enable `Orchestrator` to classify task handlers purely mathematically (via 64d cosine similarity) without requiring an LLM inference step.
- Reduce vector query latency by at least 3x through prefix-filtering.

**Non-Goals:**

- We are _not_ replacing the underlying PyO3 `fastembed` model integration; we are adding a trainable projection head/slicing logic on top of it.
- We are _not_ migrating off Synapse RDF for base relational memory.

## Decisions

**1. Hierarchical Two-Stage Retrieval (Rust/Synapse):**
We will implement a `search_fractal` method in the Synapse vector store.
_Rationale:_ A preliminary scan using only the first 64 `f32` coordinates takes significantly less memory bandwidth and compute (reducing dot product ops by 75%). This aligns with the mathematical proofs of Successive Refinement.

**2. FastEmbed Projection Head (Python/Gateway):**
We will add a lightweight PyTorch/NumPy projection module in `swarmd`'s embedding generation loop.
_Rationale:_ Existing `fastembed` models are isotropic. We must project their output through a trained transformation matrix to enforce the scale-separated encoding (V5).

**3. Zero-LLM Orchestrator Routing:**
The orchestrator will determine the appropriate handler (Coder, Architect, Reviewer) by calculating the cosine similarity of the user's task against the 64d "DNA" embeddings of each agent's capability profile instead of asking GPT-4 to parse the YAML schema dynamically.
_Rationale:_ Instantly assigns tasks, saving an average of 1000 input tokens and 2-4 seconds of API latency per turn.

## Risks / Trade-offs

- **Risk:** The projection head training might overfit to the current ontology, causing drift if new agent types are added.
  → **Mitigation:** Allow online or periodic re-projection when the `swarm_schema.yaml` changes.
- **Risk:** Stage 1 filtering (64d) might incorrectly discard a valid candidate (Recall loss).
  → **Mitigation:** Benchmark the V5 alignment to ensure the 64d cluster separation ($\Delta$) is sufficient to maintain >95% Recall@1000 before Stage 2.
