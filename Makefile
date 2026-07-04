BACKEND_DIR=backend
FRONTEND_DIR=frontend
DOCKER_COMPOSE=docker compose

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

# ── Docker ─────────────────────────────────────────────────────────
.PHONY: docker-build docker-up docker-down docker-logs
docker-build: ## Build all Docker services
	$(DOCKER_COMPOSE) build
docker-up: ## Start all Docker services in background
	$(DOCKER_COMPOSE) up -d
docker-down: ## Stop all Docker services
	$(DOCKER_COMPOSE) down
docker-logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f

.PHONY: docker-migrate-db docker-db-schema
docker-migrate-db: ## Run database migrations
	$(DOCKER_COMPOSE) run --rm backend alembic upgrade head
docker-db-schema: ## Generate a new migration (usage: make docker-db-schema name="description")
	$(DOCKER_COMPOSE) run --rm backend alembic revision --autogenerate -m "$(name)"

.PHONY: docker-test-backend docker-test-frontend
docker-test-backend: ## Run backend tests in Docker
	$(DOCKER_COMPOSE) run --rm backend pytest
docker-test-frontend: ## Run frontend tests in Docker
	$(DOCKER_COMPOSE) run --rm frontend pnpm run test

.PHONY: docker-shell-backend docker-shell-frontend
docker-shell-backend: ## Open shell in backend container
	$(DOCKER_COMPOSE) run --rm backend sh
docker-shell-frontend: ## Open shell in frontend container
	$(DOCKER_COMPOSE) run --rm frontend sh

.PHONY: docker-up-mailhog docker-up-test-db
docker-up-mailhog: ## Start MailHog email server
	$(DOCKER_COMPOSE) up mailhog
docker-up-test-db: ## Start test database
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
