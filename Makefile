BACKEND_DIR=backend
FRONTEND_DIR=frontend
DOCKER_COMPOSE=docker compose
DOCKER_COMPOSE_PROD=docker compose -f docker-compose.prod.yml

.PHONY: help
help:
	@echo "Available commands:"
	@awk '/^[a-zA-Z_-]+:/{split($$1, target, ":"); print "  " target[1] "\t" substr($$0, index($$0,$$2))}' $(MAKEFILE_LIST)

# ── Local Development ──────────────────────────────────────────────
.PHONY: start-backend start-frontend
start-backend: ## Start the backend server with hot reload and watcher
	cd $(BACKEND_DIR) && ./start.sh
start-frontend: ## Start the frontend server with hot reload and watcher
	cd $(FRONTEND_DIR) && ./start.sh

# ── Testing ────────────────────────────────────────────────────────
.PHONY: test-backend test-frontend
test-backend: ## Run backend tests using pytest
	cd $(BACKEND_DIR) && uv run pytest
test-frontend: ## Run frontend tests
	cd $(FRONTEND_DIR) && pnpm run test

.PHONY: coverage-backend
coverage-backend: ## Run backend tests with coverage report
	cd $(BACKEND_DIR) && uv run coverage run -m pytest && uv run coverage report

# ── Docker (Development) ───────────────────────────────────────────
.PHONY: docker-build docker-up docker-down docker-logs
docker-build: ## Build all Docker services (dev)
	$(DOCKER_COMPOSE) build
docker-up: ## Start all Docker services in background (dev)
	$(DOCKER_COMPOSE) up -d
docker-down: ## Stop all Docker services (dev)
	$(DOCKER_COMPOSE) down
docker-logs: ## Tail logs from all services (dev)
	$(DOCKER_COMPOSE) logs -f

# ── Docker (Production) ────────────────────────────────────────────
.PHONY: docker-prod-build docker-prod-up docker-prod-down docker-prod-logs
docker-prod-build: ## Build all Docker services (production)
	$(DOCKER_COMPOSE_PROD) build
docker-prod-up: ## Start all Docker services in background (production)
	$(DOCKER_COMPOSE_PROD) up -d
docker-prod-down: ## Stop all Docker services (production)
	$(DOCKER_COMPOSE_PROD) down
docker-prod-logs: ## Tail logs from all services (production)
	$(DOCKER_COMPOSE_PROD) logs -f

# ── Docker (Migrations) ────────────────────────────────────────────
.PHONY: docker-migrate-db docker-db-schema
docker-migrate-db: ## Run database migrations (dev)
	$(DOCKER_COMPOSE) run --rm backend alembic upgrade head
docker-db-schema: ## Generate a new migration (usage: make docker-db-schema name="description")
	$(DOCKER_COMPOSE) run --rm backend alembic revision --autogenerate -m "$(name)"

.PHONY: docker-prod-migrate-db docker-prod-db-schema
docker-prod-migrate-db: ## Run database migrations (production)
	$(DOCKER_COMPOSE_PROD) run --rm backend alembic upgrade head
docker-prod-db-schema: ## Generate a new migration (production)
	$(DOCKER_COMPOSE_PROD) run --rm backend alembic revision --autogenerate -m "$(name)"

# ── Docker (Testing) ───────────────────────────────────────────────
.PHONY: docker-test-backend docker-test-frontend
docker-test-backend: ## Run backend tests in Docker (dev)
	$(DOCKER_COMPOSE) run --rm backend pytest
docker-test-frontend: ## Run frontend tests in Docker (dev)
	$(DOCKER_COMPOSE) run --rm frontend pnpm run test

.PHONY: docker-prod-test-backend docker-prod-test-frontend
docker-prod-test-backend: ## Run backend tests in Docker (production)
	$(DOCKER_COMPOSE_PROD) run --rm backend pytest
docker-prod-test-frontend: ## Run frontend tests in Docker (production)
	$(DOCKER_COMPOSE_PROD) run --rm frontend pnpm run test

# ── Docker (Shell) ─────────────────────────────────────────────────
.PHONY: docker-shell-backend docker-shell-frontend
docker-shell-backend: ## Open shell in backend container (dev)
	$(DOCKER_COMPOSE) run --rm backend sh
docker-shell-frontend: ## Open shell in frontend container (dev)
	$(DOCKER_COMPOSE) run --rm frontend sh

.PHONY: docker-prod-shell-backend docker-prod-shell-frontend
docker-prod-shell-backend: ## Open shell in backend container (production)
	$(DOCKER_COMPOSE_PROD) run --rm backend sh
docker-prod-shell-frontend: ## Open shell in frontend container (production)
	$(DOCKER_COMPOSE_PROD) run --rm frontend sh

# ── Docker (Utilities) ─────────────────────────────────────────────
.PHONY: docker-up-mailhog docker-up-test-db
docker-up-mailhog: ## Start MailHog email server (dev)
	$(DOCKER_COMPOSE) up mailhog
docker-up-test-db: ## Start test database (dev)
	$(DOCKER_COMPOSE) up db_test

# ── Code Generation ────────────────────────────────────────────────
.PHONY: generate-client
generate-client: ## Generate OpenAPI schema and regenerate TypeScript client
	cd $(BACKEND_DIR) && uv run python -m commands.generate_openapi_schema
	cd $(FRONTEND_DIR) && pnpm run generate-client

# ── Linting ────────────────────────────────────────────────────────
.PHONY: lint
lint: ## Run pre-commit hooks on all files
	pre-commit run --all-files

.PHONY: clean
clean: ## Remove build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/.next 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/.venv 2>/dev/null || true
