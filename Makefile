.DEFAULT_GOAL := help

HOST ?= 127.0.0.1
PORT ?= 8000
PID_FILE := .server.pid
LOG_FILE := server.log
UVICORN := uv run python -m uvicorn config.asgi:application --host $(HOST) --port $(PORT) --lifespan off
MANAGE := uv run python manage.py

.PHONY: help install migrate migrations up down restart status logs dev test seed \
        superuser shell stream inspector clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (uv sync)
	uv sync

migrate: ## Apply database migrations
	$(MANAGE) migrate

migrations: ## Create migrations for the api app
	$(MANAGE) makemigrations api

up: migrate ## Start the ASGI server in the background
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Already running (PID $$(cat $(PID_FILE))) at http://$(HOST):$(PORT)/api/"; \
	else \
		nohup $(UVICORN) > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE); \
		sleep 1; \
		if kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
			echo "Started (PID $$(cat $(PID_FILE))) at http://$(HOST):$(PORT)/api/ — logs: $(LOG_FILE)"; \
		else \
			echo "Failed to start, see $(LOG_FILE)"; rm -f $(PID_FILE); exit 1; \
		fi; \
	fi

down: ## Stop the background server
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		pkill -TERM -P $$(cat $(PID_FILE)) 2>/dev/null; \
		kill -TERM $$(cat $(PID_FILE)); \
		echo "Stopped (PID $$(cat $(PID_FILE)))"; \
	else \
		echo "Not running"; \
	fi
	@rm -f $(PID_FILE)

restart: down up ## Restart the background server

status: ## Show whether the server is running
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Running (PID $$(cat $(PID_FILE))) at http://$(HOST):$(PORT)/api/"; \
	else \
		echo "Not running"; \
	fi

logs: ## Follow the server log
	tail -f $(LOG_FILE)

dev: migrate ## Run the server in the foreground with auto-reload
	$(UVICORN) --reload

test: ## Run the test suite
	$(MANAGE) test

seed: ## Load demo users (idempotent)
	$(MANAGE) seed_users

superuser: ## Create an admin superuser
	$(MANAGE) createsuperuser

shell: ## Open the Django shell
	$(MANAGE) shell

stream: ## Read the NDJSON user stream (CITY=Tampa to filter)
	uv run python examples/stream_client.py $(CITY)

inspector: ## Open the MCP Inspector for the dj-users server
	npx @modelcontextprotocol/inspector uv run python mcp_server/server.py

clean: down ## Stop the server and remove caches and logs
	find . -name __pycache__ -type d -not -path './.venv/*' -prune -exec rm -rf {} +
	rm -f $(LOG_FILE)
