.PHONY: help build up down logs test format lint clean setup shell-airflow shell-api dev-install

help:
	@echo "DataForge Development Commands"
	@echo "=============================="
	@echo ""
	@echo "Setup & Infrastructure:"
	@echo "  make build              - Build Docker images"
	@echo "  make up                 - Start all services"
	@echo "  make down               - Stop all services"
	@echo "  make setup              - Full setup (build + up + init)"
	@echo ""
	@echo "Development:"
	@echo "  make dev-install        - Install local Python dependencies"
	@echo "  make test               - Run pytest suite"
	@echo "  make lint               - Run linting (flake8)"
	@echo "  make format             - Format code (black)"
	@echo "  make clean              - Remove cache files"
	@echo ""
	@echo "Debugging & Logs:"
	@echo "  make logs               - Stream all logs"
	@echo "  make logs-airflow       - Stream Airflow logs"
	@echo "  make logs-api           - Stream API logs"
	@echo "  make logs-spark         - Stream Spark logs"
	@echo "  make shell-airflow      - SSH into Airflow container"
	@echo "  make shell-api          - SSH into API container"
	@echo "  make shell-spark        - SSH into Spark Master"
	@echo ""

build:
	docker-compose -f docker/docker-compose.yml build

up:
	docker-compose -f docker/docker-compose.yml up -d
	@echo "✅ Services started"
	@echo "   Airflow:  http://localhost:8888"
	@echo "   API:      http://localhost:8000/docs"
	@echo "   Spark UI: http://localhost:8080"
	@echo "   MinIO:    http://localhost:9001"

down:
	docker-compose -f docker/docker-compose.yml down

setup: build up
	@echo "✅ DataForge setup complete!"
	@sleep 5
	@echo "Initializing PostgreSQL..."
	docker exec dataforge-postgres psql -U dataforge -d dataforge_db -c "SELECT 1;" || true

dev-install:
	pip install -r requirements.txt

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=dataforge --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

lint:
	flake8 dataforge/ --count --select=E9,F63,F7,F82 --show-source --statistics

format:
	black dataforge/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .coverage htmlcov dist build *.egg-info

logs:
	docker-compose -f docker/docker-compose.yml logs -f

logs-airflow:
	docker-compose -f docker/docker-compose.yml logs -f dataforge-airflow

logs-api:
	docker-compose -f docker/docker-compose.yml logs -f dataforge-api

logs-spark:
	docker-compose -f docker/docker-compose.yml logs -f dataforge-spark-master

shell-airflow:
	docker exec -it dataforge-airflow bash

shell-api:
	docker exec -it dataforge-api bash

shell-spark:
	docker exec -it dataforge-spark-master bash

# Run single Airflow DAG
dag-bronze:
	docker exec dataforge-airflow airflow dags test dag_bronze_ingestion 2024-01-01

dag-silver:
	docker exec dataforge-airflow airflow dags test dag_silver_transform 2024-01-01

dag-gold:
	docker exec dataforge-airflow airflow dags test dag_gold_analytics 2024-01-01

dag-full:
	docker exec dataforge-airflow airflow dags test dag_full_pipeline_orchestration 2024-01-01

# Health checks
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not ready"
	@curl -s http://localhost:8080 > /dev/null && echo "✅ Spark Master" || echo "❌ Spark Master"
	@curl -s http://localhost:9001 > /dev/null && echo "✅ MinIO" || echo "❌ MinIO"
	@docker exec dataforge-postgres pg_isready -U dataforge > /dev/null && echo "✅ PostgreSQL" || echo "❌ PostgreSQL"
