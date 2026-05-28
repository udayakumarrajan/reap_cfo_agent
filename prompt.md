You are an elite Staff Backend Engineer and Principal Systems Architect specializing in fault-tolerant, high-scale financial ledger designs and distributed systems. 

I need you to generate a production-ready, highly scannable, cleanly decoupled Python repository implementing an Event-Driven, Microservice-Based Transaction Auto-Tagging and Month-End Close Acceleration Loop for a multi-tenant expense management platform. 

To strictly enforce the Single Responsibility Principle (SRP), clean separation of concerns, and domain-driven design, you must split the codebase across two completely independent microservice directory domains communicating over a simulated asynchronous network boundary. Do not use placeholders like "# TODO". Implement every file fully.

---

### MICROSERVICE DIRECTORY STRUCTURE TO GENERATION

reap_cfo_agent/
├── pyproject.toml                 # Centralized dependency & environment manifest (uv)
│
├── erp_service/                   # MICROSERVICE 1: Core Ledger & Accounting State (No AI or Workflow logic)
│   ├── database.py                # Thread-safe InMemoryERP storing transactions & ledger balances
│   ├── outbox_publisher.py        # Background thread enforcing At-Least-Once Delivery to Workflows
│   └── app_router.py              # Mock Network Endpoint API Router for state mutation patches
│
└── workflow_service/              # MICROSERVICE 2: Compute, Orchestration, & AI Intelligence Layer
    ├── schema.py                  # Immutable Pydantic schemas for structured LLM parsing
    ├── classifier_base.py         # Abstract Strategy Base for classification engines
    ├── classifier_openai.py       # Concrete Strategy using OpenAI Structured Outputs
    ├── activities.py              # Side-Effect handlers managing network calls back to ERP service
    └── workflows.py               # Deterministic, replay-safe Temporal State Machine (HITL handling)
│
└── run_pipeline.py                # End-to-End System Bootstrap, Broker Event Loop, & E2E Simulation

---

### COMPONENT IMPLEMENTATION SPECIFICATIONS

#### 1. Root Configuration (`pyproject.toml`)
- Build a modern `pyproject.toml` configuration utilizing `hatchling` as the build backend.
- Declare pinned production dependencies inside the `dependencies` array: `temporalio`, `openai`, `pydantic`, and `loguru`.
- Enforce Python version constraints `>=3.11`.
- Explicitly declare `tool.uv` with fields `managed = true` and `package = false` to guarantee reproducible environment syncs.

#### 2. Service 1: Core Ledger (`erp_service/database.py`, `outbox_publisher.py`, `app_router.py`)
- **`database.py` (Transactional Outbox Pattern):**
  - Implement an `InMemoryERP` class maintaining standard dictionary maps for `transactions`, a list-based `outbox_table`, and tenant Charts of Accounts (CoA).
  - Provide a thread-safe `create_transaction(self, transaction_data: dict)` method enclosed in a reentrant lock block (`threading.Lock`). It must insert a raw spend transaction into the ledger ledger and append an ingestion payload into the `outbox_table` atomically in a single block.
- **`outbox_publisher.py` (Reliable Broker Delivery):**
  - Implement an asynchronous `OutboxPublisher` engine containing a background polling loop execution path. 
  - It must inspect `InMemoryERP.outbox_table` at regular intervals. When an item appears, it invokes a network client command to push the event into the Workflow service queue, removing it from the outbox table strictly *after* confirmation of a successful workflow start trigger (At-least-once delivery guarantee).
- **`app_router.py` (Gateway State Management):**
  - Provide an `AccountingGatewayRouter` mimicking API endpoints (`get_tenant_coa`, `get_historical_context`, `update_ledger_status`). This layer converts inputs and performs updates directly against the `InMemoryERP` state instance.

#### 3. Service 2: Orchestration & Agent (`workflow_service/`)
- **`schema.py`:** Define a Pydantic v2 model `TaggingDecision` to enforce strict structured schemas on the OpenAI parsing layer: `account_code` (str), `account_name` (str), `confidence_score` (float: 0.0 to 1.0), `reasoning` (str), and `requires_human_review` (bool).
- **`classifier_base.py` & `classifier_openai.py` (Strategy Pattern):**
  - Define an abstract class `BaseClassifier(ABC)` with an abstract method `async def classify(self, transaction: dict, coa: list[dict], history: list[dict]) -> TaggingDecision`.
  - Implement `OpenAIGpt4oMiniClassifier(BaseClassifier)` using `client.beta.chat.completions.parse` with `temperature=0.0` for total determinism.
  - System Prompt Constraint: Instruct the LLM that if a merchant is rare, long-tail, or ambiguous against historical context, it MUST return a `confidence_score < 0.85` and set `requires_human_review = True`. This eliminates silent miscoding errors.
- **`activities.py` (I/O Boundaries):**
  - Implement standard, isolated Temporal Activities with structured logging via `loguru`:
    - `fetch_tenant_context_activity(tenant_id: str) -> dict`: Issues a mock network request to the ERP Service Router to fetch the customer Chart of Accounts and few-shot vector context.
    - `run_llm_tagger_activity(payload: dict) -> dict`: Instantiates the OpenAI strategy, executes classification, and dumps the parsed model map output.
    - `post_to_accounting_system_activity(payload: dict) -> str`: Network client adapter that targets the ERP Service Router to alter ledger balances, switch account codes, and shift transaction flags.
    - `update_learning_loop_vectors_activity(payload: dict) -> str`: Mocks persisting human-corrected items to a local vector space store for future classification retrieval.
- **`workflows.py` (Deterministic Replay-Safe Orchestrator):**
  - Implement the `TransactionCloseWorkflow` class. It must be perfectly deterministic (no direct network HTTP clients, file system writes, or direct LLM initializations inside the workflow function).
  - Set an internal evaluation boundary `CONFIDENCE_THRESHOLD = 0.85`.
  - Provide an asynchronous execution path and a Temporal `@workflow.signal` named `human_override_signal(self, corrected_data: dict) -> None`.
  - **Orchestration Workflow State Tree Logic:**
    1. Execute `fetch_tenant_context_activity`.
    2. Execute `run_llm_tagger_activity`.
    3. If `confidence_score >= CONFIDENCE_THRESHOLD` AND `requires_human_review == False`:
       - Execute straight-through processing (STP) via `post_to_accounting_system_activity` applying the AI-selected code with a transaction status of `AUTO_POSTED`.
       - Return execution status report map.
    4. Else (Fail-safe / Maker-Checker Product Pattern):
       - Instantly invoke `post_to_accounting_system_activity` mapping the transaction code to internal `Suspense Account (Code: 7000)` and updating the ledger flag to `NEEDS_REVIEW`. This immediately balances the balance sheets while flagging anomalies in the UI dashboard.
       - Pause workflow execution indefinitely using `await workflow.wait_condition(lambda: self.is_human_reviewed)` without consuming computational system threads.
       - Upon receiving the `human_override_signal`, fire `update_learning_loop_vectors_activity` to log feedback vectors for future runs.
       - Invoke `post_to_accounting_system_activity` updating the transaction to the human-corrected ledger code and shifting status flags to `HUMAN_RESOLVED`.
       - Return execution status report map.

#### 4. End-to-End Orchestrator (`run_pipeline.py`)
- Provide a robust standalone bootstrap file at the root level that pulls the microservices together natively:
  1. Spawns an asynchronous loop hosting a local Temporal Worker listening to a custom task queue.
  2. Initializes the `InMemoryERP` database state containing a mock tenant record setup (Tenant 123 possesses ledger codes for "SaaS tools & Software" (6100) and "Marketing" (6200)).
  3. Launches the background `OutboxPublisher` event task.
  4. Dispatches two sequential writes to `erp.create_transaction()` to simulate live transactions hitting the stream:
     - **Transaction A (Happy Path):** An AWS subscription invoice amount that triggers high confidence, resulting in an automatic straight-through update to code `6100` marked as `AUTO_POSTED`.
     - **Transaction B (Ambiguous / Long-Tail Path):** A brand new long-tail merchant invoice. Verify that it safely routes to Suspense code `7000` with status `NEEDS_REVIEW`, completely halts workflow state computation, sleeps for 3 seconds to simulate an accountant analyzing the dashboard, and then dynamically invokes a `client.signal_workflow` call injecting a correction to code `6200`, successfully resolving as `HUMAN_RESOLVED`.

Ensure all generated source code includes full type hinting (`from typing import...`), uses defensive try/except handling blocks, logs transitions gracefully using `loguru`, and follows strict PEP 8 compliance. At the end of the generation, output a markdown section documenting the direct bash commands required to sync dependencies and run the program using `uv`.