# Security & Compliance Mechanisms

## Defense in Depth Strategy

The system enforces strict compliance through a multi-layered approach:

### 1. Physical Layer (Shell Guardrails)
*   **File:** `agents/tools/shell.py`
*   **Mechanism:** A `CommandGuard` class intercepts all shell commands.
*   **Allowlist:** Only commands in `SAFE_COMMANDS` (e.g., `ls`, `grep`, `pytest`) are executed.
*   **Kill Switch:** Before execution, the system checks a global "HALTED" state in Synapse.
*   **Approval Workflow:** Dangerous commands trigger a Telegram alert and require manual approval.

### 2. Cognitive Layer (Semantic Verification)
*   **File:** `agents/reviewer.py`
*   **Mechanism:** The Reviewer Agent verifies code changes against formal rules.
*   **Knowledge Graph:** Queries Synapse for `nist:HardConstraint` triples.
*   **Neurosymbolic Check:** An LLM analyzes the diff specifically for compliance with these constraints.

### 3. Process Layer (Workflow Enforcement)
*   **Mechanism:** The Trello/OpenSpec workflow mandates a specific sequence (Spec -> Design -> Code).
*   **Files:** `openspec/specs/*.yaml`, `openspec/changes/*.md`.
*   **Role Separation:** The `ProductManager` defines specs, `Architect` designs, and `Coder` implements, preventing unilateral changes.
