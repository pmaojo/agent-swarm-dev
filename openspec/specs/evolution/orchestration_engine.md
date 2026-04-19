# Propuesta de Evolución: Migración a Microservicios Rust (Orchestration Engine)

## Análisis y Contexto

Al revisar el repositorio `agent-swarm-dev` y los logs de ejecución en Synapse, he identificado los 3 módulos de Python con mayor carga computacional y latencia:

1.  **`OrchestratorAgent` (`sdk/python/agents/orchestrator.py`)**: Este agente gestiona el flujo principal del enjambre (Swarm Flow), la toma de decisiones basada en grafos de estado y el enrutamiento complejo ("Zero-LLM Routing" usando Fractal Search). Estas operaciones requieren alta concurrencia y un uso intensivo de CPU que Python maneja ineficientemente debido al GIL.

2.  **`AnalystAgent` (`sdk/python/agents/analyst.py`)**: Este agente se encarga de analizar resultados de pruebas, generar reglas (Golden Rules), validar esquemas Turtle (.ttl) y optimizar prompts (`optimize_prompt`). Las manipulaciones intensivas de cadenas y expresiones regulares para la optimización de prompts consumen muchos ciclos de CPU y generan latencia.

3.  **`LLMService` (`sdk/python/lib/llm.py`)**: Este servicio centraliza todas las llamadas al LLM. Gestiona colas de peticiones con `threading.Lock` para evitar errores `429 Too Many Requests`, implementa cachés LRU en memoria, calcula hashes MD5 para las claves de caché y realiza seguimiento del presupuesto de tokens. Esta lógica de enrutamiento y caché es un cuello de botella crítico para la concurrencia general del sistema.

<!-- @synapse:rule Target: OrchestratorAgent, AnalystAgent, LLMService -->
<!-- @synapse:rule Inefficiency Detected: Cuellos de botella en procesamiento concurrente (GIL de Python), manipulación intensiva de strings/regex y latencia de serialización JSON/gRPC en el enrutamiento central. -->
<!-- @synapse:rule TDD Status: Red -->
<!-- @synapse:rule Synapse Tag Injected: Migrar la lógica de orquestación, análisis y enrutamiento LLM de Python a servicios gRPC nativos en Rust (`orchestration-engine`) para reducir la sobrecarga de CPU y latencia. -->

## Propuesta

De acuerdo con la preferencia hacia un repositorio centrado en Rust, propongo crear un nuevo crate en el entorno de Synapse Engine llamado `orchestration-engine`. Este crate contendrá los microservicios independientes que reemplazarán la lógica actual de Python.

## Diseño Técnico

El `orchestration-engine` será un servicio basado en Rust (usando `tonic` para gRPC) que proporcionará los siguientes servicios en puertos distintos, de forma que los clientes en Python (y futuros clientes) puedan conectarse de manera asíncrona:

1.  **Orchestrator Service (Puerto 50054)**:
    *   Gestionará la lógica de la máquina de estados.
    *   Integrará `fast_classify_stack` implementando nativamente la lógica de Zero-LLM Routing conectándose con `semantic-engine`.
    *   Definición en `orchestrator.proto`: `service OrchestratorService`.

2.  **Analyst Service (Puerto 50055)**:
    *   Implementará un analizador de rendimiento y formateador de strings super-rápido en Rust para reemplazar `optimize_prompt`.
    *   Generación de reglas estructuradas basadas en patrones.
    *   Definición en `orchestrator.proto`: `service AnalystService`.

3.  **LLM Gateway Service (Puerto 50056)**:
    *   Una pasarela asíncrona robusta (usando Tokio) para gestionar el rate-limiting con canales y actores.
    *   Caché LRU integrada en Rust (ej. usando el crate `moka` o similar) para maximizar la velocidad de caché hits.
    *   Definición en `orchestrator.proto`: `service LlmGatewayService`.

### Integración vía gRPC con el Orchestrator en Python

Los componentes de Python se reducirán a simples clientes gRPC asíncronos que delegan el trabajo intensivo a Rust. Las definiciones actuales en `orchestrator_pb2_grpc.py` ya se están conectando a estos puertos en local.

Ejemplo simplificado de integración para el LLM Gateway:
```python
# sdk/python/lib/llm.py (Refactorizado)
def connect_llm_gateway_service(self):
    self.llm_gateway_channel = grpc.insecure_channel("localhost:50056")
    self.llm_gateway_stub = orchestrator_pb2_grpc.LlmGatewayServiceStub(self.llm_gateway_channel)
```

Al migrar a este diseño, aprovecharemos la concurrencia sin hilos de Tokio y reduciremos la sobrecarga de latencia que afecta los flujos de trabajo actuales.
