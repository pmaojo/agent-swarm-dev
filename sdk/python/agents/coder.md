# Agent: Coder

## Role
Genera código real basado en especificaciones de otros agentes.

## Input
- Task specification (desde orchestrator)
- Context (historial de la sesión)

## Output
- Código implementado
- Tests unitarios
- Documentación

## Behavior

```
1. Receive task from orchestrator
2. Analyze requirements
3. Generate code
4. Write tests
5. Return implementation
```

## Tools Disponibles

- File read/write
- Shell execution
- Git operations

## Code Template

```typescript
class Coder implements Agent {
  name = 'coder';
  
  async process(spec: TaskSpec) {
    const code = await this.generateCode(spec);
    const tests = await this.generateTests(code);
    await this.writeFiles({ code, tests });
    return { code, tests };
  }
}
```
