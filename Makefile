.PHONY: help install dev-install format lint check test clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@egrep '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	poetry install

dev-install: ## Install development dependencies
	poetry install --with dev
	poetry run pre-commit install

format: ## Format code with black and isort
	poetry run black .
	poetry run isort .

lint: ## Run linting with flake8
	poetry run flake8 .

check: ## Run all checks (format + lint)
	poetry run black --check .
	poetry run isort --check-only .
	poetry run flake8 .

pre-commit: ## Run pre-commit hooks manually
	poetry run pre-commit run --all-files

clean: ## Clean up cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
