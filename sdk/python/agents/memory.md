# Agent: Memory Agent (Synapse)

## Role
Gestiona la memoria a largo plazo del swarm usando Synapse.

## Input
- Observaciones, hechos, contexto

## Output
- Triples RDF ingestados
- Consultas al grafo

## Integration

```python
from synapse import get_client

client = get_client()
client.ingest_triples([
    {"subject": "agent_coder", "predicate": "completed", "object": "task_123"}
], namespace="swarm")
```

## Tools

### add_observation
- Añade un triple al grafo
- Uso: `python3 synapse_agent.py observe '{"subject": "...", "predicate": "...", "object": "..."}'`

### query_knowledge
- Consulta el grafo
- Uso: `python3 synapse_agent.py query '{"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"}'`

## Namespace
- `swarm`: Memoria del swarm
- `agents`: Estado de agentes
- `tasks`: Tareas y resultados
