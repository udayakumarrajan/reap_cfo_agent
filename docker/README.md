# Container deployment

Local and CI environments run the full platform stack via Compose:

| Service | Responsibility |
|---------|----------------|
| `postgresql` | Persistence for Temporal Server |
| `temporal` | Workflow orchestration (gRPC `:7233`) |
| `temporal-ui` | Operations UI for workflow inspection |
| `app` | CFO Agent — ERP API, Temporal worker, transactional outbox |

## Requirements

- Docker Engine 24+ and Compose v2

## Configuration

Copy the repository environment template and adjust values:

```bash
cp .env.example .env
```

Compose substitutes variables from the project root `.env` file. For containerized runs, override at minimum:

| Variable | Compose value |
|----------|----------------|
| `TEMPORAL_ADDRESS` | `temporal:7233` |
| `DATABASE_URL` | `sqlite:////data/ledger.db` |

`OPENAI_API_KEY` defaults to `mock-key` in Compose when unset (deterministic mock classifier).

## Operations

From the repository root:

```bash
# Foreground
docker compose -f docker/compose.yml up --build

# Detached
docker compose -f docker/compose.yml up --build -d

# Tear down
docker compose -f docker/compose.yml down

# Tear down including volumes (resets Temporal + application ledger)
docker compose -f docker/compose.yml down -v
```

### Endpoints (default publish)

| Endpoint | URL |
|----------|-----|
| ERP HTTP API & dashboard | http://localhost:8000 |
| Temporal Web UI | http://localhost:8080 |

### Health

The application container blocks startup until Temporal accepts gRPC connections (`docker/entrypoint.sh`).

## Artifact layout

```
docker/
├── compose.yml    # Multi-service stack
├── Dockerfile     # Application image (build context: repo root)
├── entrypoint.sh  # Startup gate on Temporal readiness
└── README.md      # This file
```

Build context and ignore rules live at the repository root (`.dockerignore`).
