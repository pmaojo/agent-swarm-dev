## ADDED Requirements

### Requirement: Fractal Prefix Generation

The system SHALL generate embeddings where the first 64 dimensions reliably encode coarse category/domain information, and the full 256/1024 dimensions encode specific item details.

#### Scenario: Validating dimension decomposition

- **WHEN** an embedding is generated for a task "Write python script for math"
- **THEN** dimension subset `[0:64]` MUST cluster strongly with the `Coder` domain
- **THEN** dimension subset `[64:256]` MUST contain the specific Python refinement

### Requirement: Two-Stage Hierarchical Retrieval

The Synapse vector engine SHALL implement a two-stage retrieval process to optimize query latency and compute.

#### Scenario: Fast coarse filtering

- **WHEN** a semantic search is executed on the graph
- **THEN** Stage 1 MUST calculate cosine similarity using only the first 64 `f32` coordinates
- **THEN** Stage 1 MUST return the top `K*10` candidates
- **THEN** Stage 2 MUST recalculate similarity on the candidates using all 256 dimensions and return the final top `K`

### Requirement: Zero-LLM Orchestrator Routing

The Orchestrator agent SHALL route tasks to specialized handler agents using 64d semantic matching instead of relying on a Large Language Model inference step.

#### Scenario: Instant task assignment

- **WHEN** the user inputs "Create a REST API"
- **THEN** the Orchestrator MUST embed the task description
- **THEN** the Orchestrator MUST compute the similarity between the task's 64d prefix and the predefined 64d capability prefixes of all agents
- **THEN** the `Coder` agent MUST be selected without calling the OpenAI/LLM API
- **THEN** the assignment latency MUST be under 500ms

### Requirement: Fog of War Resolution

The Agent Swarm UI/Visualizer SHALL expose vector information hierarchically based on the exploration state (Fog of War) of the knowledge graph.

#### Scenario: Exploring distant concepts

- **WHEN** an agent encounters an unexplored/distant semantic node
- **THEN** the system MUST only expose the first 64 dimensions (giving a coarse "blur" of the concept's domain)
- **WHEN** the agent actively investigates the node
- **THEN** the system MUST reveal the full 256 dimensions, pulling the concept into sharp focus
