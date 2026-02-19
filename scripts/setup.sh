#!/bin/bash
# DataForge Local Setup Script
# Initializes PostgreSQL, MinIO buckets, and Airflow

set -e

echo "🚀 DataForge.io Local Setup"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker
echo -e "${YELLOW}[1/5]${NC} Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker installed${NC}"

# Check Docker Compose
echo -e "${YELLOW}[2/5]${NC} Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose installed${NC}"

# Create .env file if not exists
echo -e "${YELLOW}[3/5]${NC} Configuring environment..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo -e "${GREEN}✅ Created .env file${NC}"
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# Start services
echo -e "${YELLOW}[4/5]${NC} Starting Docker services..."
docker-compose up -d
echo -e "${GREEN}✅ Services started${NC}"

# Wait for services to be healthy
echo -e "${YELLOW}[5/5]${NC} Waiting for services to be ready..."
for i in {1..30}; do
    if docker exec dataforge-postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ PostgreSQL failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Initialize Airflow
echo "Initializing Airflow..."
docker exec dataforge-airflow airflow db init

# Create admin user
docker exec dataforge-airflow airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@dataforge.io 2>/dev/null || echo "Admin user already exists"

# Create MinIO buckets
echo "Creating MinIO buckets..."
docker exec dataforge-minio mc alias set minio http://minio:9000 minioadmin minioadmin
docker exec dataforge-minio mc mb -p minio/dataforge-bronze || true
docker exec dataforge-minio mc mb -p minio/dataforge-silver || true
docker exec dataforge-minio mc mb -p minio/dataforge-gold || true

echo ""
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "Services running:"
echo "  - Airflow UI: http://localhost:8888 (admin/admin)"
echo "  - Spark Master: http://localhost:8080"
echo "  - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "Next steps:"
echo "  1. Open Airflow at http://localhost:8888"
echo "  2. Create a pipeline config in dataforge_core/pipelines/configs/"
echo "  3. Submit a Spark job"
echo ""
