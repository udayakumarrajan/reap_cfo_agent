COMPOSE_FILE := docker/compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)

.PHONY: help up up-d down down-v logs build smoke eval

help:
	@echo "Targets:"
	@echo "  make up      Start stack (foreground, build)"
	@echo "  make up-d    Start stack (detached, build)"
	@echo "  make down    Stop stack"
	@echo "  make down-v  Stop stack and remove volumes"
	@echo "  make logs    Follow application logs"
	@echo "  make build   Build application image"
	@echo "  make smoke   Run ERP HTTP smoke script (host)"
	@echo "  make eval    Run offline tagging classifier eval (mock)"

up:
	$(COMPOSE) up --build

up-d:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f app

build:
	$(COMPOSE) build app

smoke:
	python scripts/smoke_erp.py

eval:
	uv run python scripts/eval_tagging.py
