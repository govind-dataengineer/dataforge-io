.PHONY: help setup build test lint format clean deploy logs shell

help:
	@echo "DataForge.io Makefile"
	@echo "===================="
	@echo ""
	@echo "Available targets:"
	@echo "  make setup           - Initialize local development environment"
	@echo "  make build           - Build Docker images"
	@echo "  make up              - Start Docker Compose services"
	@echo "  make down            - Stop Docker Compose services"
	@echo "  make test            - Run unit tests"
	@echo "  make lint            - Run linters (pylint, black)"
	@echo "  make format          - Auto-format code with black"
	@echo "  make clean           - Clean up temporary files"
	@echo "  make logs-airflow    - View Airflow logs"
	@echo "  make logs-spark      - View Spark logs"
	@echo "  make shell-airflow   - Open Airflow container shell"
	@echo "  make shell-spark     - Open Spark container shell"
	@echo ""

setup:
	@bash scripts/setup.sh

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Services started. Airflow UI: http://localhost:8888"

down:
	docker-compose down

test:
	@echo "Running tests..."
	docker exec dataforge-core python -m pytest tests/ -v --cov=dataforge_core

lint:
	@echo "Linting Python code..."
	docker exec dataforge-core pylint dataforge_core tests

format:
	@echo "Formatting code with black..."
	docker exec dataforge-core black dataforge_core tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .coverage htmlcov dist build *.egg-info

logs-airflow:
	docker-compose logs -f dataforge-airflow

logs-spark:
	docker-compose logs -f dataforge-spark-master

shell-airflow:
	docker exec -it dataforge-airflow bash

shell-spark:
	docker exec -it dataforge-spark-master bash

dbt-run:
	docker exec dataforge-dbt dbt run --profiles-dir /opt/dbt

dbt-test:
	docker exec dataforge-dbt dbt test --profiles-dir /opt/dbt

validate-config:
	python scripts/validate_configs.py

deploy-dev:
	@echo "Deploying to development environment..."
	terraform -chdir=infra/azure init
	terraform -chdir=infra/azure plan -var-file=dev.tfvars

deploy-prod:
	@echo "Deploying to production environment..."
	terraform -chdir=infra/azure init
	terraform -chdir=infra/azure plan -var-file=prod.tfvars
