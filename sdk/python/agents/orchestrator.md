# Agent: Orchestrator

## Role
Coordina el flujo de trabajo entre agentes usando el patrón de handoff de Anthropic Swarm.

## Input
- User request (string)

## Output
- Task breakdown (array de tareas)
- Agent assignment (qué agente maneja cada tarea)

## Behavior

```
1. Receive user request
2. Analyze and decompose into subtasks
3. Assign each subtask to appropriate agent
4. Monitor execution
5. Handle handoffs between agents
6. Return final result
```

## Handoffs

- `coder`: Para generación de código
- `reviewer`: Para revisión
- `deployer`: Para despliegue

## Code Template

```typescript
interface Agent {
  name: string;
  process(input: string): Promise<string>;
  handoff(agent: Agent, context: string): Promise<string>;
}

class Orchestrator implements Agent {
  name = 'orchestrator';
  
  async process(input: string) {
    const tasks = this.decompose(input);
    for (const task of tasks) {
      await this.assign(task);
    }
    return this.compileResults();
  }
  
  async handoff(agent: Agent, context: string) {
    return agent.process(context);
  }
}
```
